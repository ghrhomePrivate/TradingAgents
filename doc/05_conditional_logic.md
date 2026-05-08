# tradingagents/graph/conditional_logic.py 文件摘要

**文件路径**: `tradingagents/graph/conditional_logic.py`  
**代码行数**: 67 行  
**核心类**: `ConditionalLogic`

## 文件定位

定义了 LangGraph 工作流中所有条件跳转逻辑。虽然代码量不大，但对整个系统行为有决定性影响——它控制了"谁在什么时候把控制权交给谁"。

## 核心类：`ConditionalLogic`

### 初始化参数

- `max_debate_rounds`：研究辩论最大轮次（默认 1）
- `max_risk_discuss_rounds`：风险辩论最大轮次（默认 1）

### Analyst 条件方法

四个方法结构完全相同，只是目标节点名称不同：

- `should_continue_market(state)`
- `should_continue_social(state)`
- `should_continue_news(state)`
- `should_continue_fundamentals(state)`

判断逻辑：

- 如果最后一条消息包含 `tool_calls` -> 跳到对应的 `tools_*` 节点
- 否则 -> 跳到对应的 `Msg Clear *` 节点

这实现了"analyst 持续调用工具直到完成"的循环模式。

### 研究辩论条件方法

`should_continue_debate(state)` 的判断逻辑：

- 如果 `investment_debate_state["count"] >= 2 * max_debate_rounds` -> `"Research Manager"`（辩论结束）
- 如果最新回复以 "Bull" 开头 -> `"Bear Researcher"`
- 否则 -> `"Bull Researcher"`

这实现了 bull/bear 交替发言，直到达到上限。

### 风险辩论条件方法

`should_continue_risk_analysis(state)` 的判断逻辑：

- 如果 `risk_debate_state["count"] >= 3 * max_risk_discuss_rounds` -> `"Portfolio Manager"`（辩论结束）
- 如果最新发言者以 "Aggressive" 开头 -> `"Conservative Analyst"`
- 如果最新发言者以 "Conservative" 开头 -> `"Neutral Analyst"`
- 否则 -> `"Aggressive Analyst"`

这实现了三方轮流发言（aggressive -> conservative -> neutral），直到达到上限。

## 关键设计点

- **有界性**：所有循环都有明确上限，不会无限递归
- **确定性**：跳转完全由 state 中的字段值决定，没有随机性
- **轮次计算方式**：
  - 研究辩论：2 人 × N 轮 = `2 * max_debate_rounds` 次发言
  - 风险辩论：3 人 × N 轮 = `3 * max_risk_discuss_rounds` 次发言
- **修改影响大**：任何对这个文件的修改都会直接改变整个工作流的行为路径
