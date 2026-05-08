# tradingagents/agents/utils/agent_states.py 文件摘要

**文件路径**: `tradingagents/agents/utils/agent_states.py`  
**代码行数**: 73 行  
**核心类**: `AgentState`、`InvestDebateState`、`RiskDebateState`

## 文件定位

定义了整个系统共享的状态数据模型。这是"全局数据契约"，所有图节点的读写都围绕这些字段进行。理解这个文件就理解了"系统中流转的数据是什么"。

## 核心类

### `InvestDebateState`（研究辩论状态）

| 字段 | 类型 | 说明 |
|------|------|------|
| `bull_history` | str | bull researcher 的对话历史 |
| `bear_history` | str | bear researcher 的对话历史 |
| `history` | str | 完整对话历史 |
| `current_response` | str | 最新回复内容 |
| `judge_decision` | str | Research Manager 的最终判断 |
| `count` | int | 当前辩论轮次计数 |

### `RiskDebateState`（风险辩论状态）

| 字段 | 类型 | 说明 |
|------|------|------|
| `aggressive_history` | str | 激进分析师的对话历史 |
| `conservative_history` | str | 保守分析师的对话历史 |
| `neutral_history` | str | 中性分析师的对话历史 |
| `history` | str | 完整对话历史 |
| `latest_speaker` | str | 最近发言的分析师标识 |
| `current_aggressive_response` | str | 激进分析师最新回复 |
| `current_conservative_response` | str | 保守分析师最新回复 |
| `current_neutral_response` | str | 中性分析师最新回复 |
| `judge_decision` | str | Portfolio Manager 的最终判断 |
| `count` | int | 当前辩论轮次计数 |

### `AgentState`（主状态，继承自 `MessagesState`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `company_of_interest` | str | 正在分析的公司/ticker |
| `trade_date` | str | 交易日期 |
| `sender` | str | 发送当前消息的 agent 标识 |
| `market_report` | str | 市场分析师报告 |
| `sentiment_report` | str | 社交舆情分析师报告 |
| `news_report` | str | 新闻分析师报告 |
| `fundamentals_report` | str | 基本面分析师报告 |
| `investment_debate_state` | InvestDebateState | 研究辩论嵌套状态 |
| `investment_plan` | str | Research Manager 生成的投资计划 |
| `trader_investment_plan` | str | Trader 生成的交易方案 |
| `risk_debate_state` | RiskDebateState | 风险辩论嵌套状态 |
| `final_trade_decision` | str | Portfolio Manager 的最终决策 |
| `past_context` | str | 从记忆日志注入的历史上下文 |

## 设计特点

- **继承 `MessagesState`**：自动获得 LangGraph 的消息管理能力
- **使用 `Annotated` 类型**：每个字段带有描述性文档
- **嵌套状态设计**：辩论上下文封装为独立子类型，避免顶层状态过于扁平
- **计数器控制循环**：`count` 字段被 `ConditionalLogic` 用来判断辩论是否结束
- **扩展性**：如需新增 analyst，只需在 `AgentState` 增加对应的 `*_report` 字段

## 对其他文件的影响

- `ConditionalLogic` 读取 `count`、`current_response`、`latest_speaker` 来决定图跳转
- 所有 analyst 节点写入各自的 `*_report` 字段
- `Propagator` 在初始化时填充空白状态
- `Portfolio Manager` 读取 `risk_debate_state`、`investment_plan`、`trader_investment_plan`、`past_context`
