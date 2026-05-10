"""TradingAgents Web UI — Main Gradio application.

Launch with:
    tradingagents-web          (entry point)
    tradingagents web          (CLI subcommand)
    python -m web.app          (direct)
"""

from __future__ import annotations

import os
import sys
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

try:
    import gradio as gr
except ImportError:
    print(
        "ERROR: Gradio is not installed. Install web extras with:\n"
        "  uv sync --extra web\n"
        "or:\n"
        "  uv pip install gradio>=5.0"
    )
    sys.exit(1)

from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.enterprise", override=False)

logger = logging.getLogger(__name__)

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.events import AnalysisEventBus, EventType
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS

from web.analysis_runner import (
    ANALYST_AGENT_NAMES,
    ANALYST_ORDER,
    ALL_TEAMS,
    build_config,
    run_analysis_thread,
)
from web.exporter import export_markdown, export_pdf


# ---------------------------------------------------------------------------
# Helper: build model choices for a given provider
# ---------------------------------------------------------------------------


def get_model_choices(provider: str, mode: str) -> List[Tuple[str, str]]:
    """Get (label, value) pairs for model dropdown."""
    provider_lower = provider.lower()
    if provider_lower not in MODEL_OPTIONS:
        return []
    return MODEL_OPTIONS[provider_lower].get(mode, [])


def format_model_choices(provider: str, mode: str) -> List[str]:
    """Return list of model IDs for Gradio dropdown."""
    choices = get_model_choices(provider, mode)
    return [model_id for _, model_id in choices]


def format_model_labels(provider: str, mode: str) -> List[Tuple[str, str]]:
    """Return (label, value) for Gradio dropdown with labels."""
    return get_model_choices(provider, mode)


# ---------------------------------------------------------------------------
# Helper: history browser
# ---------------------------------------------------------------------------


def list_history_entries() -> List[str]:
    """Scan results_dir for past analysis reports."""
    results_dir = Path(DEFAULT_CONFIG["results_dir"])
    entries = []
    if not results_dir.exists():
        return entries
    for ticker_dir in sorted(results_dir.iterdir()):
        if not ticker_dir.is_dir():
            continue
        for date_dir in sorted(ticker_dir.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            report_file = date_dir / "reports" / "complete_report.md"
            # Also check for save_report_to_disk format
            if not report_file.exists():
                # Look for complete_report.md directly
                for f in date_dir.rglob("complete_report.md"):
                    report_file = f
                    break
            if report_file.exists():
                entries.append(f"{ticker_dir.name} / {date_dir.name}")
    return entries


def load_history_report(entry: str) -> str:
    """Load a historical report by entry string."""
    if not entry:
        return "*未选择报告。*"
    parts = entry.split(" / ")
    if len(parts) != 2:
        return "*选择无效。*"
    ticker, date = parts[0].strip(), parts[1].strip()
    results_dir = Path(DEFAULT_CONFIG["results_dir"])
    date_dir = results_dir / ticker / date
    if not date_dir.exists():
        return f"*未找到报告目录：{date_dir}*"

    # Try multiple locations
    for candidate in [
        date_dir / "reports" / "complete_report.md",
        date_dir / "complete_report.md",
    ]:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")

    # Try recursive search
    for f in date_dir.rglob("complete_report.md"):
        return f.read_text(encoding="utf-8")

    return "*该目录下未找到 complete_report.md。*"


# ---------------------------------------------------------------------------
# Main Gradio App
# ---------------------------------------------------------------------------


def create_app() -> gr.Blocks:
    """Create the Gradio Blocks application."""

    # Agent name translation for display
    AGENT_CN = {
        "Market Analyst": "市场分析师",
        "Social Analyst": "社交情绪分析师",
        "News Analyst": "新闻分析师",
        "Fundamentals Analyst": "基本面分析师",
        "Bull Researcher": "多头研究员",
        "Bear Researcher": "空头研究员",
        "Research Manager": "研究主管",
        "Trader": "交易员",
        "Aggressive Analyst": "激进风控分析师",
        "Neutral Analyst": "中性风控分析师",
        "Conservative Analyst": "保守风控分析师",
        "Portfolio Manager": "投资组合经理",
    }
    STATUS_CN = {
        "pending": "等待中",
        "in_progress": "进行中",
        "completed": "已完成",
        "cancelled": "已中断",
    }

    with gr.Blocks(
        title="TradingAgents 智能交易分析",
        theme=gr.themes.Soft(),
    ) as app:
        # Hidden state to store report data for export
        export_state = gr.State(value={"reports": {}, "ticker": "", "date": ""})
        # Hidden state to hold the cancel event for the current analysis run
        cancel_state = gr.State(value=None)
        gr.Markdown(
            "# TradingAgents 智能交易分析\n"
            "多智能体 LLM 金融交易分析框架\n\n"
            "*分析师团队 → 研究团队 → 交易员 → 风控团队 → 投资组合经理*"
        )

        with gr.Tabs():
            # ===== Tab 1: Analysis =====
            with gr.Tab("分析"):
                with gr.Row():
                    # ----- Left column: Configuration -----
                    with gr.Column(scale=1):
                        gr.Markdown("### 参数配置")
                        ticker_input = gr.Textbox(
                            label="股票代码",
                            placeholder="例如：AAPL, SPY, TSLA, 0700.HK",
                            value="SPY",
                        )
                        date_input = gr.Textbox(
                            label="分析日期（YYYY-MM-DD）",
                            placeholder="2025-01-15",
                            value=datetime.now().strftime("%Y-%m-%d"),
                        )
                        provider_dropdown = gr.Dropdown(
                            label="LLM 服务商",
                            choices=["openai", "anthropic", "google", "xai"],
                            value="openai",
                        )
                        quick_model_dropdown = gr.Dropdown(
                            label="快速思考模型",
                            choices=format_model_choices("openai", "quick"),
                            value="gpt-5.4-mini",
                        )
                        deep_model_dropdown = gr.Dropdown(
                            label="深度思考模型",
                            choices=format_model_choices("openai", "deep"),
                            value="gpt-5.4",
                        )
                        analyst_checkboxes = gr.CheckboxGroup(
                            label="分析师选择",
                            choices=["market", "social", "news", "fundamentals"],
                            value=["market", "social", "news", "fundamentals"],
                        )
                        depth_slider = gr.Slider(
                            label="研究深度（辩论轮数）",
                            minimum=1,
                            maximum=3,
                            step=1,
                            value=1,
                        )
                        language_dropdown = gr.Dropdown(
                            label="报告输出语言",
                            choices=[
                                "English",
                                "Chinese",
                                "Japanese",
                                "Korean",
                                "Spanish",
                                "French",
                                "German",
                            ],
                            value="Chinese",
                        )
                        start_btn = gr.Button("开始分析", variant="primary", size="lg")
                        cancel_btn = gr.Button(
                            "中断分析",
                            variant="stop",
                            size="lg",
                            interactive=False,
                        )

                    # ----- Right column: Progress -----
                    with gr.Column(scale=2):
                        gr.Markdown("### 运行进度")
                        status_display = gr.Dataframe(
                            headers=["团队", "智能体", "状态"],
                            label="智能体状态",
                            interactive=False,
                            wrap=True,
                        )
                        stats_display = gr.Markdown("*等待启动...*")
                        message_log = gr.Markdown(
                            "*分析过程中的消息将在此显示...*",
                            label="消息日志",
                        )

                # ----- Report Area -----
                gr.Markdown("### 分析报告")
                with gr.Accordion("分析师报告", open=True):
                    market_report = gr.Markdown("*等待中...*", label="市场分析")
                    sentiment_report = gr.Markdown("*等待中...*", label="社交情绪分析")
                    news_report = gr.Markdown("*等待中...*", label="新闻分析")
                    fundamentals_report = gr.Markdown("*等待中...*", label="基本面分析")

                with gr.Accordion("研究与交易", open=True):
                    research_report = gr.Markdown("*等待中...*", label="研究团队决策")
                    trading_report = gr.Markdown("*等待中...*", label="交易计划")

                with gr.Accordion("风控分析", open=True):
                    risk_aggressive_report = gr.Markdown(
                        "*等待中...*", label="激进风控分析师"
                    )
                    risk_conservative_report = gr.Markdown(
                        "*等待中...*", label="保守风控分析师"
                    )
                    risk_neutral_report = gr.Markdown(
                        "*等待中...*", label="中性风控分析师"
                    )
                    risk_debate_history_display = gr.Markdown(
                        "*等待中...*", label="风控辩论记录"
                    )
                    risk_pm_report = gr.Markdown(
                        "*等待中...*", label="投资组合经理决策"
                    )

                with gr.Accordion("最终决策", open=True):
                    final_decision_display = gr.Markdown(
                        "*最终投资组合决策将在此显示...*"
                    )

                # ----- Export Area -----
                gr.Markdown("### 导出报告")
                with gr.Row():
                    export_md_btn = gr.Button(
                        "导出 Markdown",
                        variant="secondary",
                        size="sm",
                    )
                    export_pdf_btn = gr.Button(
                        "导出 PDF",
                        variant="secondary",
                        size="sm",
                    )
                with gr.Row():
                    export_md_file = gr.File(
                        label="Markdown 文件",
                        visible=False,
                    )
                    export_pdf_file = gr.File(
                        label="PDF 文件",
                        visible=False,
                    )

            # ===== Tab 2: History =====
            with gr.Tab("历史记录"):
                gr.Markdown("### 历史分析报告")
                history_entries = list_history_entries()
                if history_entries:
                    history_dropdown = gr.Dropdown(
                        label="选择历史分析",
                        choices=history_entries,
                    )
                    history_report = gr.Markdown("*请在上方选择一条记录查看。*")
                    history_dropdown.change(
                        fn=load_history_report,
                        inputs=[history_dropdown],
                        outputs=[history_report],
                    )
                else:
                    gr.Markdown("*暂无历史分析记录。请先运行一次分析。*")

        # ----- Event handlers -----

        def update_models(provider):
            """Update model dropdowns when provider changes."""
            quick_choices = format_model_choices(provider, "quick")
            deep_choices = format_model_choices(provider, "deep")
            quick_val = quick_choices[0] if quick_choices else ""
            deep_val = deep_choices[0] if deep_choices else ""
            return (
                gr.update(choices=quick_choices, value=quick_val),
                gr.update(choices=deep_choices, value=deep_val),
            )

        provider_dropdown.change(
            fn=update_models,
            inputs=[provider_dropdown],
            outputs=[quick_model_dropdown, deep_model_dropdown],
        )

        def run_analysis_generator(
            ticker: str,
            analysis_date: str,
            provider: str,
            quick_model: str,
            deep_model: str,
            analysts: List[str],
            depth: int,
            language: str,
        ) -> Generator:
            """Generator that yields Gradio updates as analysis progresses.

            Each yield must be a tuple of ALL 19 output components in order:
            (status_display, stats_display, message_log,
             market_report, sentiment_report, news_report, fundamentals_report,
             research_report, trading_report,
             risk_aggressive_report, risk_conservative_report,
             risk_neutral_report, risk_debate_history_display, risk_pm_report,
             final_decision_display,
             export_state, start_btn, cancel_btn, cancel_state)
            """

            # Validate inputs
            _no_change = gr.update()
            _error_tuple_tail = (
                {"reports": {}, "ticker": "", "date": ""},
                gr.update(),  # start_btn unchanged
                gr.update(),  # cancel_btn unchanged
                None,  # cancel_state
            )
            if not ticker.strip():
                yield (
                    _no_change,
                    "**错误：** 请输入股票代码。",
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    *_error_tuple_tail,
                )
                return
            if not analysis_date.strip():
                yield (
                    _no_change,
                    "**错误：** 请输入分析日期。",
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    _no_change,
                    *_error_tuple_tail,
                )
                return

            # Build config
            config = build_config(
                ticker=ticker.strip(),
                analysis_date=analysis_date.strip(),
                llm_provider=provider,
                quick_model=quick_model,
                deep_model=deep_model,
                research_depth=int(depth),
                output_language=language,
            )

            # Create event bus, cancel event, and start analysis thread
            event_bus = AnalysisEventBus()
            cancel_event = threading.Event()
            thread = threading.Thread(
                target=run_analysis_thread,
                args=(
                    ticker.strip(),
                    analysis_date.strip(),
                    analysts,
                    config,
                    event_bus,
                    cancel_event,
                ),
                daemon=True,
            )
            thread.start()

            # Accumulated state — we yield the full state on every update
            messages: List[str] = []
            current_statuses: Dict[str, str] = {}
            stats_md = "*分析启动中...*"
            messages_md = "*等待消息...*"
            reports: Dict[str, str] = {
                "market_report": "*等待中...*",
                "sentiment_report": "*等待中...*",
                "news_report": "*等待中...*",
                "fundamentals_report": "*等待中...*",
                "investment_plan": "*等待中...*",
                "trader_investment_plan": "*等待中...*",
                "risk_aggressive": "*等待中...*",
                "risk_conservative": "*等待中...*",
                "risk_neutral": "*等待中...*",
                "risk_debate_history": "*等待中...*",
                "risk_pm_decision": "*等待中...*",
                "final_trade_decision": "*最终投资组合决策将在此显示...*",
            }
            status_rows = []

            def _build_tuple(
                btn_start=gr.update(),
                btn_cancel=gr.update(),
                cancel_st=cancel_event,
            ):
                """Build the full 19-element output tuple from current state."""
                return (
                    status_rows,
                    stats_md,
                    messages_md,
                    reports["market_report"],
                    reports["sentiment_report"],
                    reports["news_report"],
                    reports["fundamentals_report"],
                    reports["investment_plan"],
                    reports["trader_investment_plan"],
                    reports["risk_aggressive"],
                    reports["risk_conservative"],
                    reports["risk_neutral"],
                    reports["risk_debate_history"],
                    reports["risk_pm_decision"],
                    reports["final_trade_decision"],
                    {
                        "reports": dict(reports),
                        "ticker": ticker.strip(),
                        "date": analysis_date.strip(),
                    },
                    btn_start,
                    btn_cancel,
                    cancel_st,
                )

            # Yield initial state: disable start, enable cancel
            yield _build_tuple(
                btn_start=gr.update(interactive=False, value="分析中..."),
                btn_cancel=gr.update(interactive=True),
            )

            # Stream events
            cancel_pending_since: Optional[float] = None
            _CANCEL_TIMEOUT = 120  # seconds to wait after cancel before force-ending
            for event in event_bus.stream(timeout=0.5):
                changed = False

                # ── Cancel timeout guard ──
                # If cancel was requested but CANCELLED event hasn't arrived
                # within the timeout, force-end the generator so the UI
                # doesn't hang forever waiting for a blocked LLM call.
                if event.data.get("cancel_pending") or (
                    cancel_event is not None and cancel_event.is_set()
                ):
                    if cancel_pending_since is None:
                        cancel_pending_since = time.time()
                    elif (time.time() - cancel_pending_since) > _CANCEL_TIMEOUT:
                        stats_md = (
                            f"⚠️ **分析已强制中断**（等待超时） | "
                            f"**已用时：** {int((time.time() - cancel_pending_since + _CANCEL_TIMEOUT) // 60):02d}:"
                            f"{int((time.time() - cancel_pending_since + _CANCEL_TIMEOUT) % 60):02d}"
                        )
                        for agent, st in current_statuses.items():
                            if st == "in_progress":
                                current_statuses[agent] = "cancelled"
                        rows = []
                        for team, agents in ALL_TEAMS.items():
                            for agent in agents:
                                if agent in current_statuses:
                                    status = current_statuses[agent]
                                    icon = {
                                        "pending": "⏳",
                                        "in_progress": "🔄",
                                        "completed": "✅",
                                        "cancelled": "⚠️",
                                    }.get(status, "❓")
                                    agent_cn = AGENT_CN.get(agent, agent)
                                    status_cn = STATUS_CN.get(status, status)
                                    rows.append([team, agent_cn, f"{icon} {status_cn}"])
                        status_rows = rows
                        yield _build_tuple(
                            btn_start=gr.update(interactive=True, value="开始分析"),
                            btn_cancel=gr.update(interactive=False),
                        )
                        return

                if event.type == EventType.AGENT_STATUS:
                    current_statuses = event.data.get("all_statuses", current_statuses)
                    # Log risk-related status changes for debugging
                    risk_agents = [
                        "Aggressive Analyst",
                        "Conservative Analyst",
                        "Neutral Analyst",
                        "Portfolio Manager",
                    ]
                    risk_statuses = {
                        a: current_statuses.get(a, "?") for a in risk_agents
                    }
                    logger.debug("[UI] AGENT_STATUS risk=%s", risk_statuses)
                    rows = []
                    for team, agents in ALL_TEAMS.items():
                        for agent in agents:
                            if agent in current_statuses:
                                status = current_statuses[agent]
                                icon = {
                                    "pending": "⏳",
                                    "in_progress": "🔄",
                                    "completed": "✅",
                                }.get(status, "❓")
                                agent_cn = AGENT_CN.get(agent, agent)
                                status_cn = STATUS_CN.get(status, status)
                                rows.append([team, agent_cn, f"{icon} {status_cn}"])
                    status_rows = rows
                    changed = True

                elif event.type == EventType.STATS_UPDATE:
                    elapsed = event.data.get("elapsed", 0)
                    stats_md = (
                        f"**LLM 调用：** {event.data.get('llm_calls', 0)} | "
                        f"**工具调用：** {event.data.get('tool_calls', 0)} | "
                        f"**Token：** {event.data.get('tokens_in', 0)}↑ "
                        f"{event.data.get('tokens_out', 0)}↓ | "
                        f"**已用时：** {int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
                    )
                    if event.data.get("cancel_pending"):
                        stats_md += (
                            " | ⏳ **中断请求已收到，等待当前 LLM 调用完成后停止…**"
                        )
                    changed = True

                elif event.type == EventType.MESSAGE:
                    ts = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
                    msg = (
                        f"`{ts}` [{event.data.get('type', '?')}] "
                        f"{event.data.get('content', '')[:100]}"
                    )
                    messages.append(msg)
                    messages_md = "\n\n".join(messages[-15:])
                    changed = True

                elif event.type == EventType.TOOL_CALL:
                    ts = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
                    msg = f"`{ts}` [Tool] {event.data.get('name', '?')}"
                    messages.append(msg)
                    messages_md = "\n\n".join(messages[-15:])
                    changed = True

                elif event.type == EventType.REPORT_SECTION:
                    section = event.data.get("section", "")
                    content = event.data.get("content", "")
                    logger.debug(
                        "[UI] REPORT_SECTION section=%s len=%d", section, len(content)
                    )
                    if section in reports:
                        reports[section] = content
                    if section == "final_trade_decision":
                        reports[section] = f"## 最终决策\n\n{content}"
                    changed = True

                elif event.type == EventType.ANALYSIS_COMPLETE:
                    final = event.data.get("final_decision", "")
                    risk_details = event.data.get("risk_details", {})
                    logger.info(
                        "[UI] ANALYSIS_COMPLETE final_decision len=%d, risk_details keys=%s",
                        len(final) if final else 0,
                        list(risk_details.keys()),
                    )
                    # Log current report state for debugging
                    logger.info(
                        "[UI] Before backfill: risk_pm=%s final_trade=%s",
                        reports.get("risk_pm_decision", "")[:30],
                        reports.get("final_trade_decision", "")[:30],
                    )
                    # ALWAYS populate final decision and PM decision from
                    # the completed analysis state — this is the ultimate
                    # safety net regardless of whether REPORT_SECTION events
                    # were processed during streaming.
                    if final:
                        reports["final_trade_decision"] = f"## 最终决策\n\n{final}"
                        reports["risk_pm_decision"] = final
                    # Backfill risk sections from the final state.
                    # Unconditionally overwrite — the final state is the
                    # most accurate source of truth.
                    for rkey in (
                        "risk_aggressive",
                        "risk_conservative",
                        "risk_neutral",
                        "risk_debate_history",
                        "risk_pm_decision",
                    ):
                        if rkey in risk_details and risk_details[rkey]:
                            reports[rkey] = risk_details[rkey]
                    # Final fallback: if final_trade_decision is still a
                    # placeholder after everything, use risk_pm_decision.
                    if reports.get("final_trade_decision", "").startswith("*"):
                        pm_content = risk_details.get(
                            "risk_pm_decision", ""
                        ) or reports.get("risk_pm_decision", "")
                        if pm_content and not pm_content.startswith("*"):
                            reports["final_trade_decision"] = (
                                f"## 最终决策\n\n{pm_content}"
                            )
                    logger.info(
                        "[UI] After backfill: risk_pm=%s final_trade=%s",
                        reports.get("risk_pm_decision", "")[:50],
                        reports.get("final_trade_decision", "")[:50],
                    )
                    elapsed = event.data.get("elapsed", 0)
                    s = event.data.get("stats", {})
                    pm_len = len(reports.get("risk_pm_decision", ""))
                    ftd_len = len(reports.get("final_trade_decision", ""))
                    stats_md = (
                        f"✅ **分析完成！** | "
                        f"**LLM 调用：** {s.get('llm_calls', 0)} | "
                        f"**工具调用：** {s.get('tool_calls', 0)} | "
                        f"**Token：** {s.get('tokens_in', 0)}↑ "
                        f"{s.get('tokens_out', 0)}↓ | "
                        f"**总用时：** {int(elapsed // 60):02d}:{int(elapsed % 60):02d} | "
                        f"PM={pm_len} FTD={ftd_len}"
                    )
                    # Mark all completed
                    for team, agents in ALL_TEAMS.items():
                        for agent in agents:
                            if agent in current_statuses:
                                current_statuses[agent] = "completed"
                    rows = []
                    for team, agents in ALL_TEAMS.items():
                        for agent in agents:
                            if agent in current_statuses:
                                agent_cn = AGENT_CN.get(agent, agent)
                                rows.append([team, agent_cn, "✅ 已完成"])
                    status_rows = rows
                    yield _build_tuple(
                        btn_start=gr.update(interactive=True, value="开始分析"),
                        btn_cancel=gr.update(interactive=False),
                    )
                    return

                elif event.type == EventType.ANALYSIS_CANCELLED:
                    elapsed = event.data.get("elapsed", 0)
                    s = event.data.get("stats", {})
                    stats_md = (
                        f"⚠️ **分析已中断** | "
                        f"**LLM 调用：** {s.get('llm_calls', 0)} | "
                        f"**工具调用：** {s.get('tool_calls', 0)} | "
                        f"**Token：** {s.get('tokens_in', 0)}↑ "
                        f"{s.get('tokens_out', 0)}↓ | "
                        f"**已用时：** {int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
                    )
                    # Mark in_progress agents as cancelled
                    for agent, st in current_statuses.items():
                        if st == "in_progress":
                            current_statuses[agent] = "cancelled"
                    rows = []
                    for team, agents in ALL_TEAMS.items():
                        for agent in agents:
                            if agent in current_statuses:
                                status = current_statuses[agent]
                                icon = {
                                    "pending": "⏳",
                                    "in_progress": "🔄",
                                    "completed": "✅",
                                    "cancelled": "⚠️",
                                }.get(status, "❓")
                                agent_cn = AGENT_CN.get(agent, agent)
                                status_cn = STATUS_CN.get(status, status)
                                rows.append([team, agent_cn, f"{icon} {status_cn}"])
                    status_rows = rows
                    yield _build_tuple(
                        btn_start=gr.update(interactive=True, value="开始分析"),
                        btn_cancel=gr.update(interactive=False),
                    )
                    return

                elif event.type == EventType.ANALYSIS_ERROR:
                    stats_md = f"❌ **错误：** {event.data.get('error', '未知错误')}"
                    yield _build_tuple(
                        btn_start=gr.update(interactive=True, value="开始分析"),
                        btn_cancel=gr.update(interactive=False),
                    )
                    return

                if changed:
                    yield _build_tuple()

        # Wire up the start button
        start_btn.click(
            fn=run_analysis_generator,
            inputs=[
                ticker_input,
                date_input,
                provider_dropdown,
                quick_model_dropdown,
                deep_model_dropdown,
                analyst_checkboxes,
                depth_slider,
                language_dropdown,
            ],
            outputs=[
                status_display,
                stats_display,
                message_log,
                market_report,
                sentiment_report,
                news_report,
                fundamentals_report,
                research_report,
                trading_report,
                risk_aggressive_report,
                risk_conservative_report,
                risk_neutral_report,
                risk_debate_history_display,
                risk_pm_report,
                final_decision_display,
                export_state,
                start_btn,
                cancel_btn,
                cancel_state,
            ],
        )

        # ----- Cancel handler -----

        def _do_cancel(cancel_ev: Optional[threading.Event]) -> Any:
            """Set the cancel event to interrupt the running analysis."""
            if cancel_ev is not None:
                cancel_ev.set()
            return gr.update(interactive=False, value="正在中断...")

        cancel_btn.click(
            fn=_do_cancel,
            inputs=[cancel_state],
            outputs=[cancel_btn],
        )

        # ----- Export handlers -----

        def _do_export_md(state: Dict[str, Any]) -> Any:
            """Export current report as Markdown file."""
            reports_data = state.get("reports", {})
            ticker = state.get("ticker", "")
            date = state.get("date", "")
            if not reports_data or all(
                (v.startswith("*") and v.endswith("*")) for v in reports_data.values()
            ):
                # No report data yet — return nothing
                return gr.update(visible=False)
            try:
                path = export_markdown(reports_data, ticker=ticker, analysis_date=date)
                return gr.update(value=path, visible=True)
            except Exception as e:
                return gr.update(visible=False)

        def _do_export_pdf(state: Dict[str, Any]) -> Any:
            """Export current report as PDF file."""
            reports_data = state.get("reports", {})
            ticker = state.get("ticker", "")
            date = state.get("date", "")
            if not reports_data or all(
                (v.startswith("*") and v.endswith("*")) for v in reports_data.values()
            ):
                return gr.update(visible=False)
            try:
                path = export_pdf(reports_data, ticker=ticker, analysis_date=date)
                return gr.update(value=path, visible=True)
            except Exception as e:
                return gr.update(visible=False)

        export_md_btn.click(
            fn=_do_export_md,
            inputs=[export_state],
            outputs=[export_md_file],
        )
        export_pdf_btn.click(
            fn=_do_export_pdf,
            inputs=[export_state],
            outputs=[export_pdf_file],
        )

    return app


def main(
    host: str = "0.0.0.0",
    port: int = 7860,
    share: bool = False,
) -> None:
    """Launch the TradingAgents Web UI."""
    # Enable debug logging for web modules to help diagnose issues.
    # Use force=True so it works even if logging was already configured
    # by Typer, Rich, or other libraries imported earlier.
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    # Suppress noisy third-party loggers
    for noisy in (
        "httpx",
        "httpcore",
        "urllib3",
        "gradio",
        "uvicorn",
        "gradio.route_utils",
        "gradio.analytics",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    app = create_app()
    app.queue()
    app.launch(
        server_name=host,
        server_port=port,
        share=share,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TradingAgents Web UI")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=7860, help="Port to serve on")
    parser.add_argument(
        "--share", action="store_true", help="Create public Gradio link"
    )
    args = parser.parse_args()
    main(host=args.host, port=args.port, share=args.share)
