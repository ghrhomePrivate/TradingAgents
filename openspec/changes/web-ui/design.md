## Context

TradingAgents 是一个基于 LangGraph 的多 Agent 金融交易分析框架。当前仅提供 CLI 界面（Typer + Rich），用户需要在终端中逐步回答问题来配置分析参数。分析过程通过 Rich Live 布局实时展示 Agent 状态、消息流和报告内容。

核心流水线：Analyst Team → Research Team（Bull/Bear Debate）→ Trader → Risk Management（3-way Debate）→ Portfolio Manager

现有架构中，`TradingAgentsGraph` 支持通过 `graph.stream()` 流式输出 chunk，CLI 通过轮询 chunk 更新 `MessageBuffer` 状态。回调机制（`StatsCallbackHandler`）跟踪 LLM/Tool 调用统计。

项目使用 uv 作为包管理工具（已有 `uv.lock`），Python 3.10+。

## Goals / Non-Goals

**Goals:**
- 提供基于 Gradio 的 Web UI，支持浏览器访问和远程部署
- 复用现有 `TradingAgentsGraph` 核心逻辑，不修改 Agent 框架
- 实时展示分析进度（Agent 状态流转、消息流、报告生成）
- 支持多 LLM Provider/Model 选择（与 CLI 对等）
- 使用 uv 管理依赖，Web UI 作为 optional extra

**Non-Goals:**
- 不实现用户认证/多租户
- 不做并发多任务（单次 Web 请求处理一个分析任务）
- 不修改核心 Agent 逻辑或 LangGraph 图结构
- 不替换 CLI 界面（两者并存）
- 不实现付费/计费功能

## Decisions

### 1. 选择 Gradio 而非 Streamlit

**决定**：使用 Gradio 5.x

**理由**：
- Gradio 原生支持 streaming（`gr.update` + generator 模式），适合 LangGraph `stream()` 的逐 chunk 输出
- Gradio 4.x/5.x 的 `Blocks` API 提供灵活的布局能力
- Gradio 内建 Markdown 组件，适合报告渲染
- `launch(share=True)` 一键生成公网链接，便于演示
- 与 HuggingFace 生态集成好，便于后续部署

**备选方案**：
- Streamlit：rerun 模型不适合长时间流式任务，状态管理复杂
- FastAPI + React：开发量大，本次需求不需要全定制 UI

### 2. 事件流架构：抽取共享事件模块

**决定**：从 CLI 的 `MessageBuffer` 中抽取 `tradingagents/events.py` 作为 Provider-Consumer 模式的事件总线

**理由**：
- 现有 `MessageBuffer` 耦合了 Rich 渲染逻辑和状态管理
- Web UI 需要消费相同的状态变更事件
- 抽取为独立模块后，CLI 和 Web 都作为 Consumer

**设计**：
```python
# tradingagents/events.py
class AnalysisEventBus:
    """Thread-safe event bus for analysis progress."""
    def emit(self, event_type: str, data: dict): ...
    def subscribe(self, callback: Callable): ...
    def stream(self) -> Generator[dict, None, None]: ...
```

### 3. Web 模块位置

**决定**：新增 `web/` 顶层包（与 `cli/` 平级）

**理由**：
- 与 `cli/` 保持对称结构
- 独立 optional dependency，不会污染核心包
- `pyproject.toml` 中注册为 `tradingagents-web` 入口

### 4. 依赖管理

**决定**：`gradio` 作为 optional dependency，通过 `uv sync --extra web` 安装

**理由**：
- 不强制所有用户安装 Gradio（体积较大）
- 项目已使用 uv，保持一致
- `uv.lock` 会锁定 web extra 的依赖版本

### 5. 实时进度推送方案

**决定**：使用 Gradio 的 generator 模式 + `gr.update()` 实现流式 UI 更新

**理由**：
- Gradio 5.x 的 `yield` 模式原生支持 streaming output
- 无需额外 WebSocket 或 SSE 基础设施
- Agent 状态通过 `AnalysisEventBus.stream()` 逐事件 yield 给前端组件

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Gradio 大版本更新可能破坏 API | 锁定 `gradio>=5.0,<6.0`，在 CI 中固定测试 |
| 长时间分析（5-10分钟）可能导致 HTTP 超时 | 使用 Gradio 的 streaming 模式，前端保持连接活跃 |
| 抽取事件模块可能引入 CLI 回归 | CLI 保持原有 `MessageBuffer` 不变，仅新增事件桥接层 |
| Gradio 依赖链较重（~200MB） | 作为 optional extra，不影响核心安装体积 |
| 单进程不支持并发分析 | 明确标注 Non-Goal，后续可用队列方案扩展 |
