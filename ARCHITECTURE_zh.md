# TradingAgents 架构说明

## 概览

TradingAgents 是一个由图工作流编排的多智能体交易框架。系统架构围绕 LangGraph 工作流展开，使用一份共享状态对象在多个专职角色之间流转，包括分析师、研究员、交易员、风险分析角色和投资组合经理。

整个系统遵循清晰的职责分层：

- 入口层负责启动、交互和结果展示
- 编排层负责定义执行图
- agent 层负责角色化推理
- 工具与数据层负责外部信息获取
- 记忆、反思与 checkpoint 提供持久化和连续性

## 架构分层

### 1. 入口层

主要入口：

- `cli/main.py`
- `main.py`

职责：

- 加载环境变量和配置
- 收集用户输入
- 初始化 `TradingAgentsGraph`
- 触发执行
- 展示进度和结果

这一层应尽量保持轻量，核心业务逻辑应沉淀在更底层模块中。

### 2. 编排层

核心文件：

- `tradingagents/graph/trading_graph.py`
- `tradingagents/graph/setup.py`
- `tradingagents/graph/conditional_logic.py`
- `tradingagents/graph/propagation.py`

职责：

- 创建 LLM client
- 组装工具节点
- 定义图节点与边
- 构造初始状态
- 管理递归上限、辩论轮次等运行控制逻辑

这一层是项目的架构骨架。

### 3. Agent 层

主要目录：

- `tradingagents/agents/analysts/`
- `tradingagents/agents/researchers/`
- `tradingagents/agents/trader/`
- `tradingagents/agents/risk_mgmt/`
- `tradingagents/agents/managers/`

职责：

- 基于当前 state 执行角色化推理
- 在需要外部信息时请求工具
- 将结果写回共享状态

### 4. 工具与数据层

主要位置：

- `tradingagents/agents/utils/agent_utils.py`
- `tradingagents/dataflows/`

职责：

- 向 agent 暴露工具式接口
- 根据配置解析具体 vendor
- 获取价格、技术指标、基本面和新闻数据

### 5. 持久化与连续性层

主要位置：

- `tradingagents/agents/utils/memory.py`
- `tradingagents/graph/reflection.py`
- `tradingagents/graph/checkpointer.py`

职责：

- 保存历史决策
- 在未来补写 pending 决策的结果
- 基于真实收益生成反思
- 保存图执行状态用于断点恢复

## 共享状态契约

系统核心状态模型定义在 `tradingagents/agents/utils/agent_states.py`。

关键字段包括：

- `company_of_interest`
- `trade_date`
- `market_report`
- `sentiment_report`
- `news_report`
- `fundamentals_report`
- `investment_plan`
- `trader_investment_plan`
- `final_trade_decision`
- `past_context`

嵌套状态包括：

- `InvestDebateState`
- `RiskDebateState`

从架构角度看，共享状态是整个图系统保持一致性的关键。任何重要扩展都应先判断：是复用现有字段，还是需要新增状态字段。

## 执行流程

### Phase 1：初始化

`TradingAgentsGraph` 在启动阶段会依次完成：

1. 加载 config 和 callbacks
2. 设置 dataflow 配置
3. 创建结果目录与缓存目录
4. 创建 deep 和 quick 两类 LLM client
5. 初始化 memory log
6. 创建 tool nodes
7. 初始化 conditional logic、setup、propagator、reflector 和 signal processor
8. 构建并编译 LangGraph workflow

### Phase 2：构建初始状态

`Propagator.create_initial_state()` 负责构造初始 `AgentState`，其中包括：

- ticker / company 上下文
- 交易日期
- 初始消息
- 空白 analyst reports
- 空白的投资辩论和风险辩论状态
- 可选的 `past_context`

### Phase 3：分析师阶段

被选中的分析师会依次执行：

1. Market Analyst
2. Social Analyst
3. News Analyst
4. Fundamentals Analyst

实际执行哪些 analyst 取决于用户选择。

每个 analyst 遵循相同模式：

1. 读取 state
2. 执行当前任务推理
3. 如有需要则请求工具
4. 接收工具结果
5. 继续推理
6. 写出最终报告片段
7. 清理临时消息状态
8. 将控制权移交到下一个阶段

### Phase 4：研究对抗

Bull Researcher 和 Bear Researcher 会围绕投资价值展开辩论。

路由逻辑：

- 如果辩论轮次上限尚未达到，则在 bull 和 bear 之间交替
- 达到上限后，进入 `Research Manager`

`Research Manager` 会把这一阶段收敛为 `investment_plan`。

### Phase 5：交易员综合

`Trader` 将研究结论转化为可执行的交易建议，并写入 `trader_investment_plan`。

这一阶段承担研究输出与风险讨论之间的桥接职责。

### Phase 6：风险辩论

风险阶段包含三个角色：

- Aggressive Analyst
- Conservative Analyst
- Neutral Analyst

路由逻辑会在三者之间循环，直到达到设定的风险讨论轮次上限，然后进入 `Portfolio Manager`。

### Phase 7：最终决策

`Portfolio Manager` 会综合以下信息：

- research plan
- trader proposal
- risk debate history
- 可选的历史经验 `past_context`

然后生成最终决策，并尽量通过结构化输出写入 `final_trade_decision`。

## 控制流规则

控制流规则位于 `tradingagents/graph/conditional_logic.py`。

关键规则包括：

- analyst 节点在没有 tool calls 之前会持续循环
- 研究辩论上限为 `2 * max_debate_rounds`
- 风险辩论上限为 `3 * max_risk_discuss_rounds`

这些规则虽然简单，但对整个系统行为有决定性影响。任何修改都会改变整体执行路径。

## LLM 策略

框架内部维护两条模型通道：

- `quick_think_llm`
- `deep_think_llm`

设计意图是：

- 使用更快、更便宜的模型处理迭代性 agent 推理
- 将更强的推理资源保留给综合决策类角色

此外，provider 特定参数会在初始化时通过配置注入。

## Checkpoint 策略

Checkpoint 是可选能力，通过 SQLite 实现。

特点：

- 每个 ticker 一个独立 checkpoint 数据库
- 线程 ID 由 ticker 和 date 确定性生成
- 提供存在检查和清理函数

这种设计使得任务恢复能力更易实现，同时避免全局竞争。

## 记忆策略

记忆系统会先保存决策，再在未来价格数据可用时补全结果。

架构价值体现在：

- 保存跨运行的交易历史
- 支持基于真实收益的复盘反思
- 把历史经验重新注入未来决策

这是项目的一个差异化能力，因为它赋予了后续运行更强的历史上下文。

## 扩展点

### 新增 Analyst

推荐步骤：

1. 在 `tradingagents/agents/` 下实现新的 agent factory
2. 在工具抽象层增加该角色需要的工具
3. 在 `GraphSetup.setup_graph()` 中注册该角色
4. 如果需要独立报告字段，则扩展 `AgentState`
5. 如果要让用户可选，则同步更新 CLI 选择逻辑

### 新增数据 Vendor

推荐步骤：

1. 在 `tradingagents/dataflows/` 中实现 vendor 逻辑
2. 通过配置路由接入现有抽象层
3. 更新 `tradingagents/default_config.py`
4. 验证各工具函数是否正确解析 vendor

### 新增 LLM Provider

推荐步骤：

1. 在 `tradingagents/llm_clients/` 中增加新的 client
2. 在 `tradingagents/llm_clients/factory.py` 中注册
3. 处理 provider 特定参数
4. 测试普通输出和结构化输出路径

### 修改最终决策 Schema

推荐步骤：

1. 更新 `tradingagents/agents/schemas.py` 中的 schema
2. 更新 `Portfolio Manager` 渲染逻辑
3. 验证 signal extraction 是否仍然正常
4. 确认 memory log 解析逻辑未被破坏

## 架构热点

以下文件对整体架构影响最大：

- `tradingagents/graph/trading_graph.py`
- `tradingagents/graph/setup.py`
- `tradingagents/graph/conditional_logic.py`
- `tradingagents/agents/utils/agent_states.py`
- `tradingagents/agents/managers/portfolio_manager.py`

这些位置一旦变动，下游影响通常比较广。

## 设计优势

- 编排层与角色层职责分离清晰
- 图工作流比单体 prompt chaining 更易扩展
- 共享 typed state 提供了良好的结构清晰度
- provider abstraction 和 vendor abstraction 降低了耦合
- memory 和 checkpoint 提升了连续性与鲁棒性

## 设计约束

- 系统行为分布在多个层次和文件中
- 调试时需要同时理解状态流转和工具调用
- 新增角色往往需要同时修改 state、graph setup、CLI 和文档

## 推荐阅读顺序

1. `tradingagents/graph/trading_graph.py`
2. `tradingagents/graph/setup.py`
3. `tradingagents/agents/utils/agent_states.py`
4. `tradingagents/agents/managers/portfolio_manager.py`
5. `tradingagents/default_config.py`

## 最后结论

理解 TradingAgents 最好的方式，不是把它当作一组 prompt，而是把它看成一个有状态的图系统。它的核心围绕一个总编排对象、一份 typed shared state，以及一条把原始市场上下文逐步转化为最终投资组合决策的阶段式执行链路。
