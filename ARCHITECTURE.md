# TradingAgents Architecture

## Overview

TradingAgents is a graph-orchestrated multi-agent trading framework. The architecture is organized around a LangGraph workflow that moves a shared state object through a sequence of specialized roles: analysts, researchers, trader, risk analysts, and portfolio manager.

The system is designed to separate concerns cleanly:

- entrypoints handle user interaction and bootstrapping
- orchestration defines the execution graph
- agent modules implement role-specific reasoning
- tool and data layers provide external context
- memory, reflection, and checkpointing add persistence and continuity

## Architectural Layers

### 1. Entry Layer

Primary entrypoints:

- `cli/main.py`
- `main.py`

Responsibilities:

- load environment and config
- collect user inputs
- instantiate `TradingAgentsGraph`
- trigger execution
- render progress and results

This layer should stay thin. Business logic belongs lower in the stack.

### 2. Orchestration Layer

Primary files:

- `tradingagents/graph/trading_graph.py`
- `tradingagents/graph/setup.py`
- `tradingagents/graph/conditional_logic.py`
- `tradingagents/graph/propagation.py`

Responsibilities:

- create LLM clients
- assemble tool nodes
- define graph nodes and edges
- build initial state
- manage execution controls such as recursion and debate rounds

This layer is the architectural backbone of the project.

### 3. Agent Layer

Primary areas:

- `tradingagents/agents/analysts/`
- `tradingagents/agents/researchers/`
- `tradingagents/agents/trader/`
- `tradingagents/agents/risk_mgmt/`
- `tradingagents/agents/managers/`

Responsibilities:

- convert current state into role-specific reasoning
- request tools when external information is needed
- write structured outputs back into shared state

### 4. Tool and Data Layer

Primary areas:

- `tradingagents/agents/utils/agent_utils.py`
- `tradingagents/dataflows/`

Responsibilities:

- expose tool-like interfaces to agents
- resolve vendor routing from config
- fetch price, indicator, fundamentals, and news data

### 5. Persistence and Continuity Layer

Primary areas:

- `tradingagents/agents/utils/memory.py`
- `tradingagents/graph/reflection.py`
- `tradingagents/graph/checkpointer.py`

Responsibilities:

- store historical decisions
- resolve pending outcomes later
- generate reflections from realized performance
- persist graph state for resumable runs

## Shared State Contract

The central state model lives in `tradingagents/agents/utils/agent_states.py`.

Important fields include:

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

Nested state objects:

- `InvestDebateState`
- `RiskDebateState`

Architecturally, this shared state is what keeps the graph coherent. Every significant extension should begin by checking whether it needs new state fields or can reuse existing ones.

## Execution Flow

## Phase 1: Initialization

`TradingAgentsGraph` performs the following startup sequence:

1. load config and callbacks
2. set dataflow config
3. create results/cache directories
4. create deep and quick LLM clients
5. initialize memory log
6. create tool nodes
7. initialize conditional logic, setup, propagator, reflector, and signal processor
8. build and compile the LangGraph workflow

## Phase 2: Initial State Creation

`Propagator.create_initial_state()` constructs the initial `AgentState` with:

- company/ticker context
- trade date
- message seed
- blank analyst reports
- empty investment and risk debate state
- optional `past_context`

## Phase 3: Analyst Pass

Selected analysts run in sequence:

1. Market Analyst
2. Social Analyst
3. News Analyst
4. Fundamentals Analyst

The exact list depends on user selection.

Each analyst follows the same loop:

1. read state
2. reason about current task
3. request tools if needed
4. receive tool results
5. continue reasoning
6. write final report section
7. clear transient message state
8. hand off to next stage

## Phase 4: Research Debate

The bullish and bearish researchers debate the merits of the trade.

Routing logic:

- if debate round limit not reached, alternate between bull and bear
- once limit is reached, route to Research Manager

The Research Manager synthesizes this into `investment_plan`.

## Phase 5: Trader Synthesis

The Trader turns research conclusions into an actionable trading proposal and writes `trader_investment_plan`.

This acts as the bridge between research output and risk discussion.

## Phase 6: Risk Debate

Three risk roles participate:

- Aggressive Analyst
- Conservative Analyst
- Neutral Analyst

Routing logic cycles among them until the configured risk discussion limit is reached, then transfers control to the Portfolio Manager.

## Phase 7: Final Decision

The Portfolio Manager synthesizes:

- research plan
- trader proposal
- risk debate history
- optional memory-derived lessons

It then produces the final decision, ideally through structured output, and writes `final_trade_decision` back to state.

## Control Flow Rules

Flow control lives in `tradingagents/graph/conditional_logic.py`.

Key rules:

- analyst nodes loop until no tool calls remain
- research debate limit is `2 * max_debate_rounds`
- risk debate limit is `3 * max_risk_discuss_rounds`

These rules are simple but strategically important. Any change here alters how the whole graph behaves.

## LLM Strategy

The framework uses two model lanes:

- `quick_think_llm`
- `deep_think_llm`

Design intent:

- use cheaper/faster reasoning for iterative agent work
- reserve heavier reasoning for synthesis-heavy roles

Provider-specific tuning is injected during initialization through config-driven kwargs.

## Checkpoint Strategy

Checkpointing is optional and implemented with SQLite.

Characteristics:

- per-ticker checkpoint database
- deterministic thread IDs from ticker and date
- helpers for existence checks and cleanup

This makes resumability possible without central contention.

## Memory Strategy

The memory subsystem stores decisions first and resolves their outcomes later once future price data is available.

Architectural value:

- preserves trading history across runs
- enables outcome-based reflection
- injects prior lessons into future portfolio decisions

This is one of the differentiating features of the project because it gives later runs more historical grounding.

## Extension Points

## Add a New Analyst

Recommended steps:

1. implement a new agent factory under `tradingagents/agents/`
2. add any required tools to the tool abstraction layer
3. register the analyst in `GraphSetup.setup_graph()`
4. extend `AgentState` if the analyst needs a dedicated report field
5. update CLI selection UI if the role should be user-selectable

## Add a New Data Vendor

Recommended steps:

1. implement vendor-specific functions under `tradingagents/dataflows/`
2. route them through config-aware abstractions
3. update defaults in `tradingagents/default_config.py`
4. verify tool functions resolve the vendor correctly

## Add a New LLM Provider

Recommended steps:

1. add a client in `tradingagents/llm_clients/`
2. register it in `tradingagents/llm_clients/factory.py`
3. define any provider-specific kwargs handling
4. test both standard and structured-output paths

## Change the Final Decision Schema

Recommended steps:

1. update the schema in `tradingagents/agents/schemas.py`
2. update `Portfolio Manager` rendering logic
3. verify signal extraction still works
4. ensure memory log parsing remains compatible

## Architectural Hotspots

Files with the highest architectural leverage:

- `tradingagents/graph/trading_graph.py`
- `tradingagents/graph/setup.py`
- `tradingagents/graph/conditional_logic.py`
- `tradingagents/agents/utils/agent_states.py`
- `tradingagents/agents/managers/portfolio_manager.py`

If these change, downstream effects are likely broad.

## Design Strengths

- clear separation between orchestration and reasoning roles
- graph-based workflow is easier to extend than monolithic prompting
- shared typed state provides strong structural clarity
- provider abstraction and vendor abstraction reduce coupling
- memory and checkpointing improve continuity and resilience

## Design Constraints

- behavior is distributed across many files and layers
- debugging requires understanding both state transitions and tool usage
- adding new roles may require synchronized changes across state, graph setup, CLI, and docs

## Recommended Next Reading

1. `tradingagents/graph/trading_graph.py`
2. `tradingagents/graph/setup.py`
3. `tradingagents/agents/utils/agent_states.py`
4. `tradingagents/agents/managers/portfolio_manager.py`
5. `tradingagents/default_config.py`

## Final Takeaway

TradingAgents is best understood as a stateful graph system rather than a prompt collection. Its architecture revolves around a central orchestration object, a typed shared state, and a staged flow that progressively transforms raw market context into a final portfolio decision.
