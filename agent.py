from __future__ import annotations

from datetime import timedelta

from agent.config import AppConfig
from agent.memory import JsonMemory
from agent.orchestrator import Orchestrator
from llm.client import GeminiDecisionClient, NVIDIADecisionClient
from notifications.email import SmtpEmailSender
from tools.game_stores import EpicGamesStoreTool, SteamStoreTool
from tools.news import HackerNewsTool
from tools.rss import (
    RssTool,
    build_default_bengaluru_sources,
    build_default_deal_sources,
    build_default_game_sources,
)


def main() -> None:
    config = AppConfig.from_env()
    config.require_runtime_secrets()
    tools = []

    if config.enable_bengaluru_news:
        tools.append(
            RssTool(
                sources=build_default_bengaluru_sources(),
                limit_per_source=config.rss_limit_per_source,
                timeout_seconds=config.rss_timeout_seconds,
            )
        )

    if config.enable_deal_alerts:
        tools.append(
            RssTool(
                sources=build_default_deal_sources(),
                limit_per_source=config.rss_limit_per_source,
                timeout_seconds=config.rss_timeout_seconds,
            )
        )

    if config.enable_game_alerts:
        tools.append(
            RssTool(
                sources=build_default_game_sources(),
                limit_per_source=config.rss_limit_per_source,
                timeout_seconds=config.rss_timeout_seconds,
            )
        )

    if config.enable_game_store_apis:
        tools.extend(
            [
                SteamStoreTool(
                    country=config.steam_country,
                    language=config.steam_language,
                    min_discount_percent=config.steam_min_discount_percent,
                    max_specials=config.steam_max_specials,
                    max_new_releases=config.steam_max_new_releases,
                    timeout_seconds=config.rss_timeout_seconds,
                ),
                EpicGamesStoreTool(
                    country=config.epic_country,
                    locale=config.epic_locale,
                    max_items=config.epic_max_items,
                    timeout_seconds=config.rss_timeout_seconds,
                ),
            ]
        )

    if config.enable_hacker_news:
        tools.append(
            HackerNewsTool(
                limit=config.news_limit,
                timeout_seconds=config.news_timeout_seconds,
            )
        )

    # Initialize primary LLM client (NVIDIA for batch decisions)
    primary_llm_client = NVIDIADecisionClient(
        api_key=config.nvidia_api_key,
        model=config.nvidia_model,
        base_url=config.nvidia_base_url,
        timeout_seconds=config.nvidia_timeout_seconds,
    )

    # Initialize fallback LLM client (Gemini) if API key is provided
    fallback_llm_client = None
    if config.gemini_api_key:
        fallback_llm_client = GeminiDecisionClient(
            api_key=config.gemini_api_key,
            model=config.gemini_model,
            base_url=config.gemini_base_url,
            timeout_seconds=config.gemini_timeout_seconds,
        )

    orchestrator = Orchestrator(
        tools=tools,
        llm_client=primary_llm_client,
        notification_sender=SmtpEmailSender(
            smtp_server=config.smtp_server,
            smtp_port=config.smtp_port,
            username=config.email_address,
            password=config.email_password,
            recipient=config.email_to,
        ),
        memory=JsonMemory(config.state_path),
        max_event_age=timedelta(days=config.max_event_age_days),
        fallback_llm_client=fallback_llm_client,
    )
    result = orchestrator.run()
    print(result.model_dump_json())


if __name__ == "__main__":
    main()