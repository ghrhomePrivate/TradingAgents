# tradingagents/default_config.py 文件摘要

**文件路径**: `tradingagents/default_config.py`  
**代码行数**: 50 行

## 文件定位

整个框架的默认配置中心，定义了所有可配置项的初始值。这是理解系统行为的关键入口之一。

## 核心内容

### 基础目录配置

- `_TRADINGAGENTS_HOME`：`~/.tradingagents`，所有持久化数据的根目录
- `project_dir`：项目自身目录
- `results_dir`：分析结果输出目录（可通过环境变量 `TRADINGAGENTS_RESULTS_DIR` 覆盖）
- `data_cache_dir`：数据缓存目录（可通过环境变量 `TRADINGAGENTS_CACHE_DIR` 覆盖）
- `memory_log_path`：交易记忆日志路径（可通过环境变量 `TRADINGAGENTS_MEMORY_LOG_PATH` 覆盖）

### LLM 相关配置

- `llm_provider`：默认 `"openai"`
- `deep_think_llm`：默认 `"gpt-5.4"`，用于综合决策类角色
- `quick_think_llm`：默认 `"gpt-5.4-mini"`，用于快速迭代类角色
- `backend_url`：默认 `None`，由各 provider 自己决定端点

### Provider 特定推理参数

- `google_thinking_level`：Google 模型的思考强度
- `openai_reasoning_effort`：OpenAI 模型的推理力度
- `anthropic_effort`：Anthropic 模型的推理力度

### 运行控制

- `checkpoint_enabled`：默认 `False`，是否启用 LangGraph checkpoint
- `output_language`：默认 `"English"`，分析报告输出语言
- `max_debate_rounds`：默认 `1`，研究辩论最大轮次
- `max_risk_discuss_rounds`：默认 `1`，风险辩论最大轮次
- `max_recur_limit`：默认 `100`，图执行最大递归深度

### 数据源路由

- `data_vendors`：按类别配置数据源，默认全部使用 `yfinance`
  - `core_stock_apis`
  - `technical_indicators`
  - `fundamental_data`
  - `news_data`
- `tool_vendors`：按工具级别覆盖类别配置（优先级更高）

### 记忆日志配置

- `memory_log_max_entries`：默认 `None`（不限制），设置后会自动淘汰最旧的已解决条目

## 设计特点

- 所有目录路径支持环境变量覆盖
- "双模型通道"设计体现在 `deep_think_llm` / `quick_think_llm` 分离
- 数据源采用"类别级 + 工具级"两层路由策略
- 默认策略偏向"开箱即用"：不需要额外 API key 即可使用 yfinance 数据
