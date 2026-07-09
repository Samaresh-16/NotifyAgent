from __future__ import annotations

from pathlib import Path

from agent.config import AppConfig


def test_config_requires_gemini_api_key() -> None:
    config = AppConfig(
        gemini_api_key="",
        gemini_model="gemini-3.5-flash",
        gemini_base_url="https://generativelanguage.googleapis.com/v1beta",
        gemini_timeout_seconds=60,
        smtp_server="smtp.example.com",
        smtp_port=587,
        email_address="me@example.com",
        email_password="password",
        email_to="me@example.com",
        state_path=Path("state/state.json"),
        news_limit=10,
        news_timeout_seconds=10,
        rss_limit_per_source=5,
        rss_timeout_seconds=10,
        enable_hacker_news=False,
        enable_bengaluru_news=True,
        enable_deal_alerts=False,
        enable_game_alerts=True,
        enable_game_store_apis=True,
        steam_country="IN",
        steam_language="english",
        steam_min_discount_percent=60,
        steam_max_specials=20,
        steam_max_new_releases=10,
        epic_country="IN",
        epic_locale="en-US",
        epic_max_items=10,
        max_event_age_days=7,
    )

    try:
        config.require_runtime_secrets()
    except RuntimeError as error:
        assert "GEMINI_API_KEY" in str(error)
    else:
        raise AssertionError("Expected missing GEMINI_API_KEY to fail.")
