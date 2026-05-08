# README.md 文件摘要

**文件路径**: `README.md`

## 文件定位

项目的对外说明文件，面向用户和开源社区，介绍框架功能、安装方式和使用方法。

## 核心内容

### 项目定位

TradingAgents 是一个模拟真实交易公司运作方式的多智能体 LLM 金融交易框架。通过部署多种专职 agent（基本面分析师、情绪分析师、技术分析师、交易员、风控团队），协同评估市场状况并做出交易决策。

### 系统角色分工

- **分析师团队**：基本面分析师、情绪分析师、新闻分析师、技术分析师
- **研究员团队**：bull researcher 和 bear researcher 通过结构化辩论平衡收益与风险
- **交易员**：整合分析师和研究员报告，决定交易时机和规模
- **风险管理和投资组合经理**：持续评估组合风险，最终批准或拒绝交易提案

### 安装方式

- 标准安装：`git clone` + `pip install .`
- Docker 安装：`docker compose run --rm tradingagents`
- 本地模型：Ollama 支持

### 支持的 LLM Provider

OpenAI、Google、Anthropic、xAI、DeepSeek、Qwen、GLM、OpenRouter、Ollama、Azure OpenAI

### 使用方式

- CLI：运行 `tradingagents` 命令进入交互式界面
- Python API：`TradingAgentsGraph(config=...).propagate("NVDA", "2026-01-15")`

### 持久化机制

- **决策日志**：每次运行自动追加到 `~/.tradingagents/memory/trading_memory.md`
- **Checkpoint 恢复**：可选，使用 SQLite 保存图状态，中断后可恢复

## 关键要点

- 项目由 TauricResearch 团队开发和维护
- 框架仅用于研究目的，不构成投资建议
- 当前版本 v0.2.4，支持结构化输出、多 provider、checkpoint resume
- 使用 LangGraph 构建，确保灵活性和模块化
