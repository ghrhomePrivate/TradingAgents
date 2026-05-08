# tests/test_memory_log.py 文件摘要

**文件路径**: `tests/test_memory_log.py`  
**代码行数**: 773 行  
**测试对象**: `TradingMemoryLog`、`Reflector`、`Portfolio Manager`、`TradingAgentsGraph`

## 文件定位

项目中覆盖面最广、最重要的测试文件。它不仅测试记忆日志本身，还验证了从存储、延迟反思到 Portfolio Manager 注入的完整生命周期，以及遗留代码移除的回归保障。

## 测试结构

### 辅助工具

- `make_log(tmp_path)`：快速创建测试用 TradingMemoryLog 实例
- `_seed_completed()`：直接写入已完成条目（绕过 API）
- `_resolve_entry()`：存储并立即解析一个条目
- `_price_df()`：构造模拟 yfinance 历史数据
- `_make_pm_state()`：构造最小化 AgentState 供 PM 节点使用
- `_structured_pm_llm()`：构造 mock LLM 并捕获 prompt 内容

### 测试类 1：`TestTradingMemoryLogCore`

测试记忆日志的基础存储和读取能力：

- 文件创建和追加写入
- 幂等性（相同 ticker+date 不重复存储）
- 批量解析多个 pending 条目
- pending 标签格式正确性
- 五档评级解析（Buy / Overweight / Hold / Sell / fallback）
- markdown 分隔符鲁棒性（决策文本中包含 `---` 不会破坏解析）
- `load_entries` 空文件和多条目场景
- `get_pending_entries` 只返回 pending 条目
- `get_past_context` 同 ticker 和跨 ticker 的上下文生成
- 条目数量限制（n_same / n_cross）
- config 为 None 时的安全降级
- 日志轮转（rotation）功能

### 测试类 2：`TestDeferredReflection`

测试延迟反思机制：

- `update_with_outcome` 替换 pending 标签为实际收益
- 反思文本正确追加
- 其他条目不受影响
- 原子写入（.tmp 文件被正确覆盖）
- 格式化往返一致性
- `Reflector.reflect_on_final_decision()` 的 LLM 调用验证
- `_fetch_returns` 在有效数据、数据不足、退市股票等场景的行为
- `_resolve_pending_entries` 跳过非当前 ticker 的条目

### 测试类 3：`TestPortfolioManagerInjection`

测试历史上下文注入到 Portfolio Manager 的完整链路：

- `past_context` 在初始状态中的存在性
- PM prompt 中包含/不包含 lessons 区段
- PM 返回的 markdown 包含正确的结构化字段
- 结构化输出不可用时的自由文本回退
- 同 ticker 优先级和跨 ticker 上下文组织
- 跨 ticker 只展示 REFLECTION 不展示完整 DECISION
- 完整 A→B→C 生命周期集成测试

### 测试类 4：`TestLegacyRemoval`

确认旧设计已被完全移除：

- `FinancialSituationMemory` 不可导入
- `rank_bm25` 未引入
- `reflect_and_remember` 方法不存在
- `create_portfolio_manager` 不接受 `memory` 参数
- 新管线下 `propagate()` 能正常完成

## 设计特点

- **测试覆盖面极广**：从底层存储到顶层 PM 注入的完整路径
- **大量 mock 使用**：隔离外部依赖（yfinance、LLM）
- **回归保障**：专门验证旧代码已清除
- **边界场景丰富**：包括 SPY 数据不足、退市股票、.tmp 文件残留等
- **集成测试**：`test_full_cycle_store_resolve_inject` 和 `test_full_pipeline_no_regression` 验证端到端流程
