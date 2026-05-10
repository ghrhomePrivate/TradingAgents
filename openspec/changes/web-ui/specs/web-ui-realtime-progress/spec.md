## ADDED Requirements

### Requirement: Real-time agent status display
The system SHALL display the current status (pending, in_progress, completed) of each Agent in real-time as the analysis progresses.

#### Scenario: Agent transitions to in_progress
- **WHEN** an Agent begins processing (e.g., Market Analyst starts)
- **THEN** the Web UI SHALL update that Agent's status indicator to "in_progress" within 2 seconds

#### Scenario: Agent completes
- **WHEN** an Agent finishes its task
- **THEN** the Web UI SHALL update that Agent's status indicator to "completed" and transition the next Agent to "in_progress"

#### Scenario: All agents complete
- **WHEN** the Portfolio Manager completes the final decision
- **THEN** all Agent status indicators SHALL show "completed" and the UI SHALL indicate the analysis is finished

### Requirement: Streaming message log
The system SHALL display a live feed of LLM messages and tool calls as they occur during analysis.

#### Scenario: New LLM message received
- **WHEN** the analysis graph emits a new Agent or Tool message
- **THEN** the message SHALL appear in the message log with timestamp and type classification

#### Scenario: Tool call logged
- **WHEN** an Agent invokes a tool (e.g., get_stock_data)
- **THEN** the tool name and arguments SHALL appear in the message log

### Requirement: Progress statistics
The system SHALL display aggregate statistics during analysis including LLM call count, tool call count, token usage, and elapsed time.

#### Scenario: Statistics update
- **WHEN** an LLM call completes with token usage metadata
- **THEN** the statistics panel SHALL update to reflect the cumulative totals

#### Scenario: Elapsed time display
- **WHEN** analysis is running
- **THEN** the elapsed time counter SHALL update every second

### Requirement: Event bus architecture
The system SHALL provide a thread-safe event bus (`AnalysisEventBus`) that decouples the analysis graph from UI consumers.

#### Scenario: Event emission
- **WHEN** the analysis graph produces a state change (agent status, message, report section)
- **THEN** the event bus SHALL emit a typed event that both CLI and Web consumers can process

#### Scenario: Stream consumption
- **WHEN** the Web UI subscribes to the event bus stream
- **THEN** it SHALL receive events in order via a generator, suitable for Gradio's yield-based streaming
