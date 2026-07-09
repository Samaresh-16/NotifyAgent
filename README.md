# AI Notifier

A scheduled personal AI notification agent that can run on GitHub Actions without a long-lived server.

The MVP collects game sale/free-game/release alerts plus Bengaluru-focused local alerts, asks Google Gemini for a structured notification decision, sends one digest email only when needed, records notified event hashes in JSON state, and exits.

## Architecture

```text
GitHub Actions cron
  -> python agent.py
  -> tools collect events
  -> LLM decides with structured output
  -> email sender sends one digest when needed
  -> JSON memory persists notified event hashes
```

## Setup

Create a Python 3.12 environment and install dependencies:

```bash
pip install -r requirements.txt
```

Required environment variables:

```bash
GEMINI_API_KEY=...
EMAIL_ADDRESS=you@gmail.com
EMAIL_PASSWORD=your-gmail-app-password
EMAIL_TO=you@gmail.com
```

Optional environment variables:

```bash
GEMINI_MODEL=gemini-3.5-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
GEMINI_TIMEOUT_SECONDS=60
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
STATE_PATH=state/state.json
ENABLE_BENGALURU_NEWS=true
ENABLE_DEAL_ALERTS=false
ENABLE_GAME_ALERTS=true
ENABLE_GAME_STORE_APIS=true
ENABLE_HACKER_NEWS=false
MAX_EVENT_AGE_DAYS=7
STEAM_COUNTRY=IN
STEAM_LANGUAGE=english
STEAM_MIN_DISCOUNT_PERCENT=60
STEAM_MAX_SPECIALS=20
STEAM_MAX_NEW_RELEASES=10
EPIC_COUNTRY=IN
EPIC_LOCALE=en-US
EPIC_MAX_ITEMS=10
RSS_LIMIT_PER_SOURCE=5
RSS_TIMEOUT_SECONDS=10
```

Run locally:

```bash
python agent.py
```

## Gemini

This project now uses only Google Gemini. Configure it with:

```bash
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash
```

The Gemini client calls the Google Generative Language API `interactions` endpoint directly with `httpx` and asks Gemini to return JSON that matches the `NotificationDecision` Pydantic schema.

## Current Sources

Enabled by default:

- Direct Steam Store API alerts for steep specials, free offers, and Steam new releases.
- Direct Epic Games Store promotions API alerts for currently claimable free games.
- Bengaluru local/civic alerts from Google News RSS searches covering traffic, power cuts, water supply, BMTC, Namma Metro, bandh, BBMP, BESCOM, BWSSB, airport, and traffic police updates.
- Game news fallback from Google News RSS searches covering Steam, Epic Games Store, EA app/Electronic Arts, Ubisoft Store, free games, giveaways, free weekends, major discounts, seasonal sales, and notable new releases.

Weather, rain, temperature, AQI, and forecast alerts are intentionally filtered out because the user already has dedicated weather apps. The agent sends at most one email per run, formatted as a digest of all interesting items.
Events older than `MAX_EVENT_AGE_DAYS` are skipped before the LLM evaluates them. The default is 7 days.

EA and Ubisoft do not currently provide a stable public free-game/deals API comparable to Steam and Epic. They remain covered by the game-news fallback. Direct EA/Ubisoft storefront scraping can be added later, but it is more brittle than API-backed collection.

Optional:

- Hacker News can be enabled with `ENABLE_HACKER_NEWS=true`, but it is off by default because it is usually not Bengaluru-specific.

These are news/deal-signal sources, not direct product price trackers. Direct price tracking for specific Amazon/Flipkart/Myntra product URLs should be added as a separate tool because those sites do not offer one shared public price-drop API.

## GitHub Actions

Add repository secrets:

- `GEMINI_API_KEY`
- `EMAIL_ADDRESS`
- `EMAIL_PASSWORD`
- `EMAIL_TO`

Optional repository variables:

- `GEMINI_MODEL`
- `GEMINI_BASE_URL`
- `ENABLE_BENGALURU_NEWS`
- `ENABLE_DEAL_ALERTS`
- `ENABLE_GAME_ALERTS`
- `ENABLE_GAME_STORE_APIS`
- `ENABLE_HACKER_NEWS`
- `MAX_EVENT_AGE_DAYS`
- `STEAM_COUNTRY`
- `STEAM_MIN_DISCOUNT_PERCENT`
- `EPIC_COUNTRY`
- `RSS_LIMIT_PER_SOURCE`

To avoid manually copy-pasting values, install GitHub CLI, authenticate once, then sync local `.env` values:

```powershell
gh auth login
.\scripts\sync_github_env.ps1
```

The script uploads `GEMINI_API_KEY`, `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, and `EMAIL_TO` as GitHub Actions secrets. Other `.env` entries are uploaded as repository variables.

The workflow in `.github/workflows/run.yml` commits `state/state.json` after successful runs so duplicate notifications are avoided on ephemeral runners.

The scheduled workflow runs nightly at 10:00 PM IST. GitHub Actions cron is written in UTC, so the workflow uses `30 16 * * *`.

To toggle scheduled runs without changing code, create or update the repository variable:

```text
ENABLE_SCHEDULED_RUN=false
```

Manual runs from the GitHub Actions UI still work when scheduled runs are disabled. Set `ENABLE_SCHEDULED_RUN=true` or delete the variable to turn the nightly run back on.

## Adding A Tool

Create a class with:

```python
def collect(self) -> list[Event]:
    ...
```

Then register it in `agent.py`. The orchestrator does not need to know anything about the tool implementation.

## Tests

```bash
pytest
```
