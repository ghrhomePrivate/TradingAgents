# cli/main.py 文件摘要

**文件路径**: `cli/main.py`  
**代码行数**: 1221 行  
**核心对象**: `app`（typer 应用）、`MessageBuffer` 类

## 文件定位

项目的交互式终端入口文件。通过 `pyproject.toml` 中的 `tradingagents = "cli.main:app"` 暴露为命令行工具。这个文件只负责用户交互和结果展示，不包含核心业务逻辑。

## 核心结构

### `MessageBuffer` 类

一个面向展示层的状态管理器，用于追踪和渲染运行过程中的各类信息。

**主要职责**：

- 管理 agent 执行状态（pending / in_progress / completed）
- 缓存消息和工具调用记录
- 维护报告区段内容（market_report、sentiment_report、news_report 等）
- 组装最终完整报告

**关键属性**：

- `FIXED_AGENTS`：固定参与的团队（Research、Trading、Risk、Portfolio）
- `ANALYST_MAPPING`：analyst 类型到显示名称的映射
- `REPORT_SECTIONS`：报告区段与 agent 完成状态的映射

**关键方法**：

- `init_for_analysis(selected_analysts)`：根据用户选择初始化状态
- `get_completed_reports_count()`：统计已完成的报告数量
- `update_agent_status(agent, status)`：更新 agent 状态
- `update_report_section(section_name, content)`：更新报告内容

### 终端布局

使用 `rich.layout.Layout` 组织三层结构：

- `header`：欢迎信息
- `main`：分为 `upper`（进度 + 消息）和 `analysis`（当前报告）
- `footer`：底部信息

### CLI 应用

使用 `typer` 框架创建命令行应用，主要功能包括：

- 收集用户输入（ticker、日期、provider、模型、analyst 选择）
- 启动 `TradingAgentsGraph` 并执行分析
- 使用 `rich.live.Live` 实时更新终端展示
- 展示最终报告和统计信息

### 统计集成

通过 `StatsCallbackHandler` 追踪执行统计：

- LLM 调用次数
- Tool 调用次数
- 输入/输出 token 数量

## 设计特点

- **展示逻辑与业务逻辑完全分离**：CLI 不参与决策推理
- **动态面板**：根据用户选择的 analyst 动态调整展示内容
- **实时更新**：使用 rich 的 Live 功能实现运行中的实时刷新
- **消息去重**：通过 `_processed_message_ids` 避免重复处理
- **报告完成判定**：不仅看内容是否非空，还要求对应 agent 状态为 "completed"
- **全局 `message_buffer`**：模块级实例，在整个 CLI 生命周期内共享状态
