## 1. Project Setup

- [ ] 1.1 Add `gradio>=5.0,<6.0` as optional dependency in `pyproject.toml` under `[project.optional-dependencies]` web group
- [ ] 1.2 Add `web/` to `[tool.setuptools.packages.find]` include list
- [ ] 1.3 Add `tradingagents-web = "web.app:main"` entry point in `[project.scripts]`
- [ ] 1.4 Run `uv sync --extra web` to install dependencies and update `uv.lock`

## 2. Event Bus Module

- [ ] 2.1 Create `tradingagents/events.py` with `AnalysisEventBus` class (thread-safe queue, emit/subscribe/stream)
- [ ] 2.2 Define event types: `AgentStatusEvent`, `MessageEvent`, `ReportSectionEvent`, `StatsEvent`, `AnalysisCompleteEvent`
- [ ] 2.3 Add unit tests for event bus in `tests/test_events.py`

## 3. Web Module Structure

- [ ] 3.1 Create `web/__init__.py`
- [ ] 3.2 Create `web/app.py` — Gradio Blocks layout with tabs (Analysis, History)
- [ ] 3.3 Create `web/components.py` — reusable Gradio component builders (config form, progress panel, report viewer)
- [ ] 3.4 Create `web/analysis_runner.py` — bridge between Gradio generator and `TradingAgentsGraph.stream()`

## 4. Configuration Form (web-ui-app)

- [ ] 4.1 Implement ticker input with validation
- [ ] 4.2 Implement date picker with future-date validation
- [ ] 4.3 Implement LLM provider dropdown with dynamic model options (import from `model_catalog.py`)
- [ ] 4.4 Implement analyst type checkboxes (Market, Social, News, Fundamentals)
- [ ] 4.5 Implement research depth selector
- [ ] 4.6 Implement "Start Analysis" button that triggers the streaming generator

## 5. Real-time Progress (web-ui-realtime-progress)

- [ ] 5.1 Implement agent status table component (Dataframe or HTML) with status indicators
- [ ] 5.2 Implement message log component (scrollable Markdown or Dataframe)
- [ ] 5.3 Implement statistics bar (LLM calls, tool calls, tokens, elapsed time)
- [ ] 5.4 Wire `analysis_runner.py` generator to yield Gradio updates on each event bus emission

## 6. Report Viewer (web-ui-report-viewer)

- [ ] 6.1 Implement tabbed/accordion Markdown display for each report section
- [ ] 6.2 Implement final decision highlight panel
- [ ] 6.3 Implement history browser — scan `results_dir` and list past analyses
- [ ] 6.4 Implement past report loader — read and render `complete_report.md`

## 7. CLI Integration

- [ ] 7.1 Add `web` subcommand to `cli/main.py` (or new `cli/web_cmd.py`) with `--port`, `--share`, `--host` options
- [ ] 7.2 Guard Gradio import behind try/except with helpful error message if web extra not installed

## 8. Testing & Validation

- [ ] 8.1 Verify `uv sync --extra web` installs Gradio successfully
- [ ] 8.2 Verify `uv sync` (without extra) does NOT install Gradio
- [ ] 8.3 Smoke test: launch Web UI and verify all form components render
- [ ] 8.4 Validate openspec change: `openspec validate web-ui`
