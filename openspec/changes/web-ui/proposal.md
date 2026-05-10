## Why

TradingAgents 目前仅有基于 Typer + Rich 的 CLI 界面，对非技术用户不友好，且无法在远程服务器上通过浏览器访问。增加 Web UI 可以降低使用门槛、支持团队协作与远程部署，并能利用浏览器原生能力（表格渲染、图表可视化、实时更新）更好地展示多 Agent 的分析流程和最终交易决策。

## What Changes

- 新增 `web/` 模块，基于 **Gradio** 构建 Web UI 应用
- 提供以下核心页面/功能：
  - **分析配置面板**：输入股票代码（Ticker）、分析日期区间；选择 LLM Provider（OpenAI / Anthropic / Google / xAI）及对应模型（Quick Think / Deep Think）；选择启用的 Analyst 类型
  - **实时进度看板**：以流式方式展示各 Agent（Analyst → Researcher → Trader → Risk → Portfolio Manager）的运行状态、当前阶段、LLM 调用日志
  - **报告展示**：Markdown 渲染各阶段报告（Market Analysis、Sentiment、News、Fundamentals、Research Decision、Trading Plan、Final Decision）
  - **历史记录**：查看过去的分析结果（复用现有 `results_dir` 中的日志）
- 新增 `tradingagents run-web` CLI 子命令，一键启动 Web 服务
- 新增 `gradio` 依赖到 `pyproject.toml`（作为 optional dependency `[web]`）
- 使用 **uv** 作为包管理工具，替代 pip 进行依赖安装与虚拟环境管理
- 抽取现有 CLI 中 `MessageBuffer` / 回调机制为可复用的事件流接口，供 Web UI 消费

## Capabilities

### New Capabilities

- `web-ui-app`: Gradio Web 应用主体，包含页面布局、组件组织、路由配置
- `web-ui-realtime-progress`: Agent 运行状态的实时流式推送机制（基于 Gradio streaming / SSE）
- `web-ui-report-viewer`: 分析报告的 Markdown 渲染与历史回看功能

### Modified Capabilities

（无现有 spec 需要修改，当前项目无 openspec/specs/ 目录）

## Impact

- **新增依赖**：`gradio>=5.0`（optional，通过 `uv pip install tradingagents[web]` 或 `uv sync --extra web` 安装）
- **包管理工具**：使用 **uv** 管理依赖和虚拟环境，利用其极速解析和 lockfile 机制（项目已有 `uv.lock`）
  - 安装命令：`uv sync --extra web`
  - 开发环境：`uv sync --all-extras`
  - 添加依赖：`uv add --optional web gradio`
- **代码改动**：
  - `cli/main.py`：抽取 `MessageBuffer` 事件处理逻辑为独立模块 `tradingagents/events.py`，CLI 和 Web 共享
  - `tradingagents/graph/trading_graph.py`：回调接口保持不变，无需修改核心图逻辑
  - `pyproject.toml`：新增 `[project.optional-dependencies]` web 组和 `tradingagents-web` 入口
- **不影响**：现有 CLI 功能、核心 Agent 逻辑、LLM 客户端、数据流模块
- **部署影响**：Web UI 可通过 `gradio` 的 share 功能生成公网链接，也可配合 Docker 部署；uv 在 CI/Docker 中同样适用（`pip install uv && uv sync`）
