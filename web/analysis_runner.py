"""Bridge between Gradio generator and TradingAgentsGraph.stream().

Runs the analysis in a background thread and emits events via the event bus,
which the Gradio frontend consumes through a generator/yield pattern.

A separate heartbeat thread periodically polls the StatsCallbackHandler and
emits STATS_UPDATE events so the Gradio UI keeps receiving updates even while
graph.stream() is blocked waiting for long-running LLM calls.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.events import AnalysisEventBus, EventType

logger = logging.getLogger(__name__)


# Agent ordering constants (shared with CLI)
ANALYST_ORDER = ["market", "social", "news", "fundamentals"]
ANALYST_AGENT_NAMES = {
    "market": "Market Analyst",
    "social": "Social Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}
ANALYST_REPORT_MAP = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}

ALL_TEAMS = {
    "分析师团队": [
        "Market Analyst",
        "Social Analyst",
        "News Analyst",
        "Fundamentals Analyst",
    ],
    "研究团队": ["Bull Researcher", "Bear Researcher", "Research Manager"],
    "交易团队": ["Trader"],
    "风控团队": [
        "Aggressive Analyst",
        "Neutral Analyst",
        "Conservative Analyst",
    ],
    "投资组合管理": ["Portfolio Manager"],
}


class _StatsHeartbeat:
    """Periodically polls StatsCallbackHandler and emits STATS_UPDATE events.

    This keeps the Gradio UI alive during long-running LLM calls where
    graph.stream() blocks and no chunks are produced.

    When a cancel_event is detected, emits MESSAGE events so the user
    sees immediate feedback that the cancellation was received while
    waiting for the current LLM call to finish.
    """

    def __init__(
        self,
        event_bus: AnalysisEventBus,
        stats_handler: Any,
        start_time: float,
        interval: float = 2.0,
        cancel_event: Optional[threading.Event] = None,
        agent_status: Optional[Dict[str, str]] = None,
    ):
        self._event_bus = event_bus
        self._stats_handler = stats_handler
        self._start_time = start_time
        self._interval = interval
        self._cancel_event = cancel_event
        self._agent_status = agent_status
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._cancel_notified = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(self._interval)
            if self._stop_event.is_set():
                break
            try:
                stats = self._stats_handler.get_stats()
                stats["elapsed"] = time.time() - self._start_time
                stats["heartbeat"] = True

                # Detect pending cancellation and notify the UI
                if self._cancel_event is not None and self._cancel_event.is_set():
                    stats["cancel_pending"] = True
                    if not self._cancel_notified:
                        self._cancel_notified = True
                        self._event_bus.emit(
                            EventType.MESSAGE,
                            {
                                "type": "System",
                                "content": "中断请求已收到，正在等待当前 LLM 调用完成…",
                            },
                        )

                self._event_bus.emit(EventType.STATS_UPDATE, stats)

                # Also re-emit current agent statuses so the UI stays
                # in sync even during long LLM calls between chunks.
                if self._agent_status is not None:
                    self._event_bus.emit(
                        EventType.AGENT_STATUS,
                        {"all_statuses": dict(self._agent_status)},
                    )
            except Exception:
                pass  # Heartbeat is best-effort


def build_config(
    ticker: str,
    analysis_date: str,
    llm_provider: str,
    quick_model: str,
    deep_model: str,
    research_depth: int = 1,
    output_language: str = "English",
) -> Dict[str, Any]:
    """Build a config dict from Web UI form inputs."""
    # Provider-specific base URLs (matching cli/utils.py PROVIDERS)
    PROVIDER_URLS = {
        "openai": "http://127.0.0.1:3002/v1",
        "anthropic": "http://127.0.0.1:3002/v1",
        "google": None,
        "xai": "https://api.x.ai/v1",
        "deepseek": "https://api.deepseek.com",
        "ollama": "http://localhost:11434/v1",
    }
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = llm_provider.lower()
    config["quick_think_llm"] = quick_model
    config["deep_think_llm"] = deep_model
    config["max_debate_rounds"] = research_depth
    config["max_risk_discuss_rounds"] = research_depth
    config["output_language"] = output_language
    config["backend_url"] = PROVIDER_URLS.get(llm_provider.lower())
    return config


def run_analysis_thread(
    ticker: str,
    analysis_date: str,
    selected_analysts: List[str],
    config: Dict[str, Any],
    event_bus: AnalysisEventBus,
    cancel_event: Optional[threading.Event] = None,
) -> None:
    """Run the analysis graph in a background thread, emitting events.

    This function is meant to be launched via threading.Thread.

    Args:
        cancel_event: If set, the analysis loop will break at the next
            chunk boundary and emit ANALYSIS_CANCELLED.
    """
    heartbeat: Optional[_StatsHeartbeat] = None
    try:
        from cli.stats_handler import StatsCallbackHandler
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        stats_handler = StatsCallbackHandler()

        event_bus.emit(
            EventType.ANALYSIS_STARTED,
            {
                "ticker": ticker,
                "date": analysis_date,
                "analysts": selected_analysts,
            },
        )

        # Initialize agent statuses
        agent_status: Dict[str, str] = {}
        for analyst_key in selected_analysts:
            if analyst_key in ANALYST_AGENT_NAMES:
                agent_status[ANALYST_AGENT_NAMES[analyst_key]] = "pending"
        for team_agents in [
            ["Bull Researcher", "Bear Researcher", "Research Manager"],
            ["Trader"],
            ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
            ["Portfolio Manager"],
        ]:
            for agent in team_agents:
                agent_status[agent] = "pending"

        # Set first analyst to in_progress
        if selected_analysts:
            first_agent = ANALYST_AGENT_NAMES.get(selected_analysts[0])
            if first_agent:
                agent_status[first_agent] = "in_progress"
                event_bus.emit(
                    EventType.AGENT_STATUS,
                    {
                        "agent": first_agent,
                        "status": "in_progress",
                        "all_statuses": dict(agent_status),
                    },
                )

        # Create graph
        if cancel_event is not None and cancel_event.is_set():
            event_bus.emit(
                EventType.ANALYSIS_CANCELLED,
                {"reason": "user_cancelled", "stats": {}, "elapsed": 0},
            )
            return

        graph = TradingAgentsGraph(
            selected_analysts,
            config=config,
            debug=True,
            callbacks=[stats_handler],
        )

        # Run analysis
        init_state = graph.propagator.create_initial_state(ticker, analysis_date)
        args = graph.propagator.get_graph_args(callbacks=[stats_handler])
        start_time = time.time()

        # Start heartbeat — keeps the UI alive during long LLM calls by
        # periodically emitting stats updates even when graph.stream() blocks.
        # Also detects pending cancel and notifies the user immediately.
        heartbeat = _StatsHeartbeat(
            event_bus=event_bus,
            stats_handler=stats_handler,
            start_time=start_time,
            interval=2.0,
            cancel_event=cancel_event,
            agent_status=agent_status,
        )
        heartbeat.start()

        report_sections: Dict[str, Optional[str]] = {}
        _emitted_sections: Dict[str, str] = {}  # Track what we've already emitted
        trace = []

        def _emit_section(section: str, content: str) -> None:
            """Emit a REPORT_SECTION event only if content has changed."""
            if not content:
                logger.debug("[_emit_section] %s: SKIPPED (empty content)", section)
                return
            if _emitted_sections.get(section) == content:
                logger.debug(
                    "[_emit_section] %s: SKIPPED (dedup, len=%d)", section, len(content)
                )
                return  # Already emitted this exact content
            logger.info("[_emit_section] %s: EMITTING (len=%d)", section, len(content))
            _emitted_sections[section] = content
            event_bus.emit(
                EventType.REPORT_SECTION,
                {"section": section, "content": content},
            )

        chunk_idx = 0
        for chunk in graph.graph.stream(init_state, **args):
            chunk_idx += 1
            # Log top-level keys for debugging
            chunk_keys = [
                k
                for k in chunk.keys()
                if isinstance(chunk.get(k), str) and chunk[k].strip()
            ]
            risk_state_summary = ""
            if chunk.get("risk_debate_state"):
                rs = chunk["risk_debate_state"]
                risk_state_summary = (
                    f"count={rs.get('count', 0)} "
                    f"speaker={rs.get('latest_speaker', '')} "
                    f"agg={bool(rs.get('aggressive_history', '').strip())} "
                    f"con={bool(rs.get('conservative_history', '').strip())} "
                    f"neu={bool(rs.get('neutral_history', '').strip())} "
                    f"judge={bool(rs.get('judge_decision', '').strip())}"
                )
            ftd_present = bool(chunk.get("final_trade_decision", ""))
            logger.info(
                "[chunk %d] str_keys=%s risk=[%s] ftd=%s",
                chunk_idx,
                chunk_keys,
                risk_state_summary,
                ftd_present,
            )
            # Check for cancellation at each chunk boundary
            if cancel_event is not None and cancel_event.is_set():
                event_bus.emit(
                    EventType.ANALYSIS_CANCELLED,
                    {
                        "reason": "user_cancelled",
                        "stats": stats_handler.get_stats(),
                        "elapsed": time.time() - start_time,
                    },
                )
                return

            # Emit stats
            stats = stats_handler.get_stats()
            stats["elapsed"] = time.time() - start_time
            event_bus.emit(EventType.STATS_UPDATE, stats)

            # Process analyst reports
            for analyst_key in ANALYST_ORDER:
                if analyst_key not in selected_analysts:
                    continue
                report_key = ANALYST_REPORT_MAP[analyst_key]
                if chunk.get(report_key):
                    report_sections[report_key] = chunk[report_key]
                    _emit_section(report_key, chunk[report_key])

            # Update analyst statuses
            found_active = False
            for analyst_key in ANALYST_ORDER:
                if analyst_key not in selected_analysts:
                    continue
                agent_name = ANALYST_AGENT_NAMES[analyst_key]
                report_key = ANALYST_REPORT_MAP[analyst_key]
                if report_sections.get(report_key):
                    agent_status[agent_name] = "completed"
                elif not found_active:
                    agent_status[agent_name] = "in_progress"
                    found_active = True

            # Research team
            if chunk.get("investment_debate_state"):
                debate = chunk["investment_debate_state"]
                if debate.get("bull_history") or debate.get("bear_history"):
                    agent_status["Bull Researcher"] = "in_progress"
                    agent_status["Bear Researcher"] = "in_progress"
                if debate.get("judge_decision"):
                    agent_status["Bull Researcher"] = "completed"
                    agent_status["Bear Researcher"] = "completed"
                    agent_status["Research Manager"] = "completed"
                    if not chunk.get("trader_investment_plan"):
                        # Only set Trader to in_progress if Trader hasn't run yet
                        agent_status["Trader"] = "in_progress"
                    _emit_section("investment_plan", debate["judge_decision"])

            # Trader
            if chunk.get("trader_investment_plan"):
                _emit_section("trader_investment_plan", chunk["trader_investment_plan"])
                if agent_status.get("Trader") != "completed":
                    agent_status["Trader"] = "completed"
                    agent_status["Aggressive Analyst"] = "in_progress"

            # ── Risk Management Team ──────────────────────────────
            # Mirror CLI logic for report emission, but improve status
            # tracking beyond what CLI does. CLI keeps all 3 risk
            # analysts at "in_progress" until PM finishes — that's
            # OK for a TUI but feels stuck in a web UI. We use
            # latest_speaker to mark each analyst completed as the
            # next one starts, and set PM to in_progress once all 3
            # are done.
            if chunk.get("risk_debate_state"):
                risk_state = chunk["risk_debate_state"]
                agg_hist = risk_state.get("aggressive_history", "").strip()
                con_hist = risk_state.get("conservative_history", "").strip()
                neu_hist = risk_state.get("neutral_history", "").strip()
                debate_hist = risk_state.get("history", "").strip()
                judge = risk_state.get("judge_decision", "").strip()
                speaker = risk_state.get("latest_speaker", "")
                count = risk_state.get("count", 0)

                # Emit report sections (dedup handles repeat chunks)
                if agg_hist:
                    _emit_section("risk_aggressive", agg_hist)
                if con_hist:
                    _emit_section("risk_conservative", con_hist)
                if neu_hist:
                    _emit_section("risk_neutral", neu_hist)
                if debate_hist:
                    _emit_section("risk_debate_history", debate_hist)

                # ── Status tracking via latest_speaker ──
                # After Aggressive runs: speaker="Aggressive", count=1
                #   → Aggressive completed, Conservative in_progress
                # After Conservative runs: speaker="Conservative", count=2
                #   → Conservative completed, Neutral in_progress
                # After Neutral runs: speaker="Neutral", count=3
                #   → Neutral completed, PM in_progress
                # After PM runs: speaker="Judge", judge=non-empty
                #   → All completed
                logger.debug(
                    "[chunk %d] risk status: speaker=%r count=%d agg=%d con=%d neu=%d judge=%d",
                    chunk_idx,
                    speaker,
                    count,
                    len(agg_hist),
                    len(con_hist),
                    len(neu_hist),
                    len(judge),
                )
                if speaker.startswith("Aggressive") and agg_hist:
                    agent_status["Aggressive Analyst"] = "completed"
                    agent_status["Conservative Analyst"] = "in_progress"
                    logger.info(
                        "[chunk %d] Aggressive completed → Conservative in_progress",
                        chunk_idx,
                    )
                elif speaker.startswith("Conservative") and con_hist:
                    agent_status["Aggressive Analyst"] = "completed"
                    agent_status["Conservative Analyst"] = "completed"
                    agent_status["Neutral Analyst"] = "in_progress"
                    logger.info(
                        "[chunk %d] Conservative completed → Neutral in_progress",
                        chunk_idx,
                    )
                elif speaker.startswith("Neutral") and neu_hist:
                    agent_status["Aggressive Analyst"] = "completed"
                    agent_status["Conservative Analyst"] = "completed"
                    agent_status["Neutral Analyst"] = "completed"
                    agent_status["Portfolio Manager"] = "in_progress"
                    logger.info(
                        "[chunk %d] Neutral completed → PM in_progress", chunk_idx
                    )
                elif speaker.startswith("Judge") or judge:
                    # PM has finished — ensure all are completed even if
                    # we detect via judge_decision before speaker check
                    agent_status["Aggressive Analyst"] = "completed"
                    agent_status["Conservative Analyst"] = "completed"
                    agent_status["Neutral Analyst"] = "completed"
                    agent_status["Portfolio Manager"] = "completed"
                    logger.info(
                        "[chunk %d] Judge detected → all risk completed", chunk_idx
                    )
                elif agg_hist and not con_hist and not neu_hist:
                    # Fallback: only aggressive history present
                    agent_status["Aggressive Analyst"] = "in_progress"
                elif count == 0 and not agg_hist:
                    # Risk debate hasn't started yet — keep as-is
                    pass
                else:
                    # Multi-round: if count > 3, analysts may be in round 2+
                    # Mark based on what we know
                    if agg_hist:
                        agent_status["Aggressive Analyst"] = "in_progress"
                    if con_hist:
                        agent_status["Conservative Analyst"] = "in_progress"
                    if neu_hist:
                        agent_status["Neutral Analyst"] = "in_progress"

                if judge:
                    logger.info(
                        "[chunk %d] PM judge_decision found (len=%d), emitting risk_pm_decision + final_trade_decision",
                        chunk_idx,
                        len(judge),
                    )
                    _emit_section("risk_pm_decision", judge)
                    _emit_section("final_trade_decision", judge)
                    agent_status["Aggressive Analyst"] = "completed"
                    agent_status["Conservative Analyst"] = "completed"
                    agent_status["Neutral Analyst"] = "completed"
                    agent_status["Portfolio Manager"] = "completed"

            # Also check top-level final_trade_decision directly.
            # PM sets both risk_debate_state.judge_decision AND
            # top-level final_trade_decision. Catch it as fallback.
            ftd = chunk.get("final_trade_decision", "")
            if isinstance(ftd, str) and ftd.strip():
                logger.info(
                    "[chunk %d] top-level final_trade_decision found (len=%d)",
                    chunk_idx,
                    len(ftd.strip()),
                )
                _emit_section("final_trade_decision", ftd.strip())
                _emit_section("risk_pm_decision", ftd.strip())
                agent_status["Portfolio Manager"] = "completed"

            # Emit updated statuses
            event_bus.emit(
                EventType.AGENT_STATUS,
                {
                    "all_statuses": dict(agent_status),
                },
            )

            # Process messages
            for message in chunk.get("messages", []):
                content = getattr(message, "content", None)
                if content and isinstance(content, str) and content.strip():
                    event_bus.emit(
                        EventType.MESSAGE,
                        {
                            "type": type(message).__name__,
                            "content": content[:200],
                        },
                    )
                if hasattr(message, "tool_calls") and message.tool_calls:
                    for tc in message.tool_calls:
                        name = tc["name"] if isinstance(tc, dict) else tc.name
                        event_bus.emit(EventType.TOOL_CALL, {"name": name})

            trace.append(chunk)

        # Analysis complete
        final_state = trace[-1] if trace else {}
        final_decision = final_state.get("final_trade_decision", "")
        logger.info(
            "Stream ended after %d chunks. final_trade_decision present=%s (len=%d)",
            len(trace),
            bool(final_decision),
            len(final_decision) if final_decision else 0,
        )

        # Extract risk debate details for backfill in the UI
        risk_final = final_state.get("risk_debate_state", {})
        risk_details = {}
        if isinstance(risk_final, dict):
            for hist_key, section_key in [
                ("aggressive_history", "risk_aggressive"),
                ("conservative_history", "risk_conservative"),
                ("neutral_history", "risk_neutral"),
                ("history", "risk_debate_history"),
                ("judge_decision", "risk_pm_decision"),
            ]:
                val = risk_final.get(hist_key, "")
                if isinstance(val, str) and val.strip():
                    risk_details[section_key] = val.strip()

        # Mark all agents complete
        for agent in agent_status:
            agent_status[agent] = "completed"
        event_bus.emit(EventType.AGENT_STATUS, {"all_statuses": dict(agent_status)})

        event_bus.emit(
            EventType.ANALYSIS_COMPLETE,
            {
                "final_decision": final_decision,
                "risk_details": risk_details,
                "final_state": {
                    k: v for k, v in final_state.items() if isinstance(v, str)
                },
                "stats": stats_handler.get_stats(),
                "elapsed": time.time() - start_time,
            },
        )

    except Exception as e:
        event_bus.emit(EventType.ANALYSIS_ERROR, {"error": str(e)})

    finally:
        if heartbeat is not None:
            heartbeat.stop()
        event_bus.close()
