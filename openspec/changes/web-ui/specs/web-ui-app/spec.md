## ADDED Requirements

### Requirement: Web UI application launch
The system SHALL provide a `tradingagents-web` CLI entry point and a `tradingagents web` subcommand that launches a Gradio-based Web UI on a configurable host and port.

#### Scenario: Default launch
- **WHEN** user runs `tradingagents web`
- **THEN** a Gradio app SHALL start on `http://localhost:7860` and open in the default browser

#### Scenario: Custom port
- **WHEN** user runs `tradingagents web --port 8080`
- **THEN** the Gradio app SHALL start on port 8080

#### Scenario: Share mode
- **WHEN** user runs `tradingagents web --share`
- **THEN** Gradio SHALL generate a public URL for remote access

### Requirement: Analysis configuration form
The system SHALL provide a configuration form that collects all parameters needed to start an analysis, equivalent to the CLI's interactive questionnaire.

#### Scenario: Ticker input
- **WHEN** user enters a stock ticker (e.g., "AAPL") in the Ticker field
- **THEN** the system SHALL validate it is a non-empty string and accept it as the analysis target

#### Scenario: Date selection
- **WHEN** user selects an analysis date
- **THEN** the system SHALL validate the date is in YYYY-MM-DD format and not in the future

#### Scenario: LLM provider selection
- **WHEN** user selects an LLM provider from the dropdown (OpenAI, Anthropic, Google, xAI)
- **THEN** the Quick Think and Deep Think model dropdowns SHALL update to show only models available for that provider

#### Scenario: Analyst selection
- **WHEN** user checks/unchecks analyst types (Market, Social, News, Fundamentals)
- **THEN** the analysis SHALL only invoke the selected analysts

#### Scenario: Start analysis
- **WHEN** user clicks "Start Analysis" with valid configuration
- **THEN** the system SHALL create a `TradingAgentsGraph` with the specified parameters and begin streaming the analysis

### Requirement: Dependency installation via uv
The web UI dependencies SHALL be installable as an optional extra using uv.

#### Scenario: Install web extra
- **WHEN** user runs `uv sync --extra web`
- **THEN** gradio and all web-related dependencies SHALL be installed into the virtual environment

#### Scenario: Core install unaffected
- **WHEN** user runs `uv sync` without the web extra
- **THEN** gradio SHALL NOT be installed, and the core CLI SHALL function normally
