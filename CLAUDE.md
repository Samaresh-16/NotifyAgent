# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup
```bash
# Create Python 3.12 environment and install dependencies
pip install -r requirements.txt

# Copy example environment file and configure
cp .env.example .env  # or manually create .env with required variables
```

### Running the Application
```bash
# Run the agent locally (requires environment variables)
python agent.py

# Run tests
pytest

# Run specific test file
pytest tests/test_orchestrator.py -v
```

### GitHub Actions Integration
The project uses GitHub Actions for scheduled runs:
- Sync local .env to GitHub secrets: `.\scripts\sync_github_env.ps1` (requires GitHub CLI)
- Scheduled workflow runs nightly at 10:00 PM IST (30 16 * * * UTC)
- Manual triggers available via workflow_dispatch
- State persistence: state/state.json is committed after successful runs

## Architecture Overview

### High-Level Flow
```
GitHub Actions cron (or manual trigger)
        → python agent.py
        → Load configuration from environment
        → Initialize tools based on feature flags
        → Orchestrator collects events from all enabled tools
        → Deduplicate events (in-run and persistent memory)
        → Filter events by age (default: max 7 days old)
        → For each event, LLM (Gemini) decides notification priority/action
        → Build single digest email from all notifications (if any)
        → Send email via SMTP (Gmail by default)
        → Update persisted state with notified event hashes
        → Exit
```

### Core Components

#### 1. `agent.py` - Main Entry Point
- Orchestrates the entire workflow
- Loads configuration via `AppConfig.from_env()`
- Initializes tools based on feature flags from `.env`
- Creates orchestrator with LLM client, email sender, and memory
- Executes orchestrator run and prints JSON result

#### 2. `agent/orchestrator.py` - Core Logic
- **Event Collection**: Gathers events from all enabled tools
- **Deduplication**: Removes duplicates within run and against persisted state
- **Age Filtering**: Skips events older than `MAX_EVENT_AGE_DAYS`
- **LLM Decision Making**: Uses Gemini to evaluate each event for notification worthiness
- **Notification Batching**: Combines all notified events into single email digest
- **State Management**: Persists notified event hashes to prevent duplicate notifications
- **Error Handling**: Continues operation despite individual tool/LLM/email failures

#### 3. **Tools** (`tools/` directory) - Event Collection
Each tool implements the `BaseTool` protocol (`collect() -> list[Event]`):
- **RSS Tools**: Collect from Google News RSS feeds (Bengaluru news, deals, games)
- **Game Store Tools**: Direct API calls to Steam and Epic Games stores
- **Hacker News Tool**: Collects from Hacker News (optional, off by default)

#### 4. **LLM Client** (`llm/client.py` - referenced)
- Uses Google Gemini via direct HTTP calls to Generative Language API
- Requests structured JSON output matching `NotificationDecision` Pydantic model
- Configured via `GEMINI_API_KEY`, `GEMINI_MODEL`, etc.

#### 5. **Notification System** (`notifications/`)
- **Email Sender**: SMTP-based email delivery (Gmail default)
- **Email Renderer**: Optional HTML email templating using Jinja2

#### 6. **Memory System** (`agent/memory.py`)
- JSON-persisted set of notified event hashes
- Prevents duplicate notifications across runs
- Automatic save/load with error handling

#### 7. **Data Models** (`agent/models.py`)
- **Event**: Represents collected information (title, source, URL, timestamp, etc.)
- **NotificationDecision**: LLM output (notify yes/no, priority 1-10, subject, body, reason)
- **AgentRunResult**: Metrics from each run (counts of collected, considered, notified, etc.)

### Key Features
- **Single Email Digest**: Combines all notifications into one email per run
- **Priority-Based Subject**: Email subject reflects highest priority item
- **Duplicate Prevention**: Persistent state prevents re-notifying same events
- **Age Filtering**: Configurable maximum age for events (default 7 days)
- **Fault Tolerance**: Continues operation if individual tools/LLM/email fail
- **Feature Flags**: Enable/disable specific alert sources via environment variables
- **Structured LLM Output**: Uses Pydantic for validated LLM responses

### Environment Configuration
Required (in `.env` or GitHub secrets):
- `GEMINI_API_KEY` - Gemini API key
- `EMAIL_ADDRESS` - Sender email address
- `EMAIL_PASSWORD` - App password for SMTP
- `EMAIL_TO` - Recipient email address

Optional Features (defaults shown):
- `ENABLE_BENGALURU_NEWS=true` - Bengaluru civic alerts
- `ENABLE_DEAL_ALERTS=false` - General deal alerts
- `ENABLE_GAME_ALERTS=true` - Game news alerts
- `ENABLE_GAME_STORE_APIS=true` - Steam/Epic store API alerts
- `ENABLE_HACKER_NEWS=false` - Hacker News (off by default)
- `MAX_EVENT_AGE_DAYS=7` - Maximum age of events to consider
- Various store-specific settings (countries, languages, limits, etc.)

### Testing Approach
- Unit tests in `tests/` directory using pytest
- Heavy use of dependency injection and faking (`FakeTool`, `FakeLlm`, `FakeSender`)
- Tests cover orchestration logic, deduplication, age filtering, error handling
- Mock external dependencies (HTTP, SMTP, LLM) for reliable testing

### Code Entry Points
- **Main**: `agent.py` - starts the entire process
- **Orchestration**: `agent/orchestrator.py` - core workflow logic
- **Tools**: Individual implementations in `tools/` directory
- **Configuration**: `agent/config.py` - environment variable parsing
- **Models**: `agent/models.py` - Pydantic data models
- **Memory**: `agent/memory.py` - JSON-persisted state
- **Notifications**: `notifications/` - email sending and rendering

### Common Development Tasks
1. **Adding a new tool**:
   - Create class implementing `BaseTool` protocol (name + collect() method)
   - Register in `agent.py` tools initialization based on feature flag
   - Add feature flag to `AppConfig` if needed
   - Add to requirements if new dependencies needed

2. **Modifying LLM behavior**:
   - Update `NotificationDecision` model if changing response structure
   - Modify prompt engineering in `GeminiDecisionClient`
   - Adjust prompt construction in orchestrator if needed

3. **Changing notification delivery**:
   - Modify `notifications/email.py` for different delivery mechanism
   - Update orchestrator's notification sending logic
   - Adjust configuration in `AppConfig` as needed

4. **Updating feature flags**:
   - Add to `AppConfig.from_env()` and dataclass fields
   - Add corresponding `.env` variable documentation in README
   - Update tool initialization logic in `agent.py`
   - Add to GitHub Actions workflow variables if needed

### Important Files Reference
- `README.md` - Comprehensive project documentation
- `.env` - Local environment variables (not committed)
- `requirements.txt` - Python dependencies
- `.github/workflows/run.yml` - GitHub Actions CI/CD configuration
- `state/state.json` - Persistent notification state (auto-generated)