## ADDED Requirements

### Requirement: Markdown report rendering
The system SHALL render each analysis report section as formatted Markdown in the Web UI.

#### Scenario: Report section available
- **WHEN** an analyst report (e.g., Market Analysis) is generated
- **THEN** the Web UI SHALL render it as Markdown in the corresponding report tab/accordion

#### Scenario: Multiple report sections
- **WHEN** multiple report sections have been generated
- **THEN** the user SHALL be able to view each section independently (tabbed or accordion layout)

### Requirement: Final decision display
The system SHALL prominently display the Portfolio Manager's final trade decision when available.

#### Scenario: Final decision rendered
- **WHEN** the final_trade_decision is available in the analysis state
- **THEN** the Web UI SHALL render it in a highlighted/prominent section separate from intermediate reports

### Requirement: Report section categories
The system SHALL organize reports into logical categories matching the analysis pipeline stages.

#### Scenario: Category organization
- **WHEN** viewing the report viewer
- **THEN** reports SHALL be grouped as: Analyst Team (Market, Social, News, Fundamentals) → Research Team → Trading Team → Risk Management → Portfolio Decision

### Requirement: History browsing
The system SHALL allow users to browse previously completed analysis reports from the results directory.

#### Scenario: List past analyses
- **WHEN** user navigates to the History tab
- **THEN** the system SHALL list all past analyses from `results_dir`, grouped by ticker and date

#### Scenario: View past report
- **WHEN** user selects a past analysis entry
- **THEN** the system SHALL load and display the complete_report.md content as rendered Markdown

#### Scenario: Empty history
- **WHEN** no past analyses exist in results_dir
- **THEN** the system SHALL display a message indicating no history is available
