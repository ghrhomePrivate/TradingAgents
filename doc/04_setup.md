# tradingagents/graph/setup.py 文件摘要

**文件路径**: `tradingagents/graph/setup.py`  
**代码行数**: 182 行  
**核心类**: `GraphSetup`

## 文件定位

负责把所有角色节点、工具节点和条件逻辑拼装成一个完整的 LangGraph `StateGraph`。这是定义"系统执行顺序"的核心文件。

## 核心类：`GraphSetup`

### 初始化

接收四个参数：

- `quick_thinking_llm`：快速推理模型实例
- `deep_thinking_llm`：深度推理模型实例
- `tool_nodes`：预构建的工具节点字典
- `conditional_logic`：`ConditionalLogic` 实例

### `setup_graph(selected_analysts)` 方法

这是最关键的方法，负责组装整个工作流图。

#### 第一步：创建 analyst 节点

根据 `selected_analysts` 列表，为每个 analyst 创建三种节点：

- 推理节点（如 `Market Analyst`）
- 消息清理节点（如 `Msg Clear Market`）
- 工具执行节点（如 `tools_market`）

#### 第二步：创建其他角色节点

- `Bull Researcher` / `Bear Researcher`（使用 quick LLM）
- `Research Manager`（使用 deep LLM）
- `Trader`（使用 quick LLM）
- `Aggressive Analyst` / `Neutral Analyst` / `Conservative Analyst`（使用 quick LLM）
- `Portfolio Manager`（使用 deep LLM）

#### 第三步：定义边（执行顺序）

整体图结构如下：

```
START -> 第一个 Analyst
Analysts 串行连接（每个 analyst 内部有 tool 循环）
最后一个 Analyst -> Bull Researcher
Bull/Bear 辩论循环 -> Research Manager
Research Manager -> Trader
Trader -> Aggressive Analyst
Aggressive/Conservative/Neutral 辩论循环 -> Portfolio Manager
Portfolio Manager -> END
```

#### 条件边

- **Analyst 条件边**：如果有 tool calls -> tool node；否则 -> 消息清理
- **研究辩论条件边**：bull/bear 交替，直到达到轮次上限 -> Research Manager
- **风险辩论条件边**：三者循环，直到达到轮次上限 -> Portfolio Manager

## 设计特点

- 动态图构建：根据用户选择的 analyst 动态生成不同的图
- LLM 资源分配策略：manager 用 deep LLM，analyst/researcher/trader 用 quick LLM
- 条件边实现了"循环 + 有界终止"的模式
- 每个 analyst 有独立的工具循环，互不干扰
- 图结构的三层模式：analyst 串行 -> 研究辩论 -> 风险辩论
