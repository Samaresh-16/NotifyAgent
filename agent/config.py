from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    gemini_api_key: str
    gemini_model: str
    gemini_base_url: str
    gemini_timeout_seconds: float
    smtp_server: str
    smtp_port: int
    email_address: str
    email_password: str
    email_to: str
    state_path: Path
    news_limit: int
    news_timeout_seconds: float
    rss_limit_per_source: int
    rss_timeout_seconds: float
    enable_hacker_news: bool
    enable_bengaluru_news: bool
    enable_deal_alerts: bool
    enable_game_alerts: bool
    enable_game_store_apis: bool
    steam_country: str
    steam_language: str
    steam_min_discount_percent: int
    steam_max_specials: int
    steam_max_new_releases: int
    epic_country: str
    epic_locale: str
    epic_max_items: int
    max_event_age_days: int
    # NVIDIA fallback configuration (optional)
    nvidia_api_key: str = ""
    nvidia_model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv()
        email_address = os.getenv("EMAIL_ADDRESS", "")
        email_to = os.getenv("EMAIL_TO") or email_address
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
            gemini_base_url=os.getenv(
                "GEMINI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta",
            ),
            gemini_timeout_seconds=float(os.getenv("GEMINI_TIMEOUT_SECONDS", "60")),
            smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            email_address=email_address,
            email_password=os.getenv("EMAIL_PASSWORD", ""),
            email_to=email_to,
            state_path=Path(os.getenv("STATE_PATH", "state/state.json")),
            news_limit=int(os.getenv("NEWS_LIMIT", "10")),
            news_timeout_seconds=float(os.getenv("NEWS_TIMEOUT_SECONDS", "10")),
            rss_limit_per_source=int(os.getenv("RSS_LIMIT_PER_SOURCE", "5")),
            rss_timeout_seconds=float(os.getenv("RSS_TIMEOUT_SECONDS", "10")),
            enable_hacker_news=_env_bool("ENABLE_HACKER_NEWS", default=False),
            enable_bengaluru_news=_env_bool("ENABLE_BENGALURU_NEWS", default=True),
            enable_deal_alerts=_env_bool("ENABLE_DEAL_ALERTS", default=False),
            enable_game_alerts=_env_bool("ENABLE_GAME_ALERTS", default=True),
            enable_game_store_apis=_env_bool("ENABLE_GAME_STORE_APIS", default=True),
            steam_country=os.getenv("STEAM_COUNTRY", "IN"),
            steam_language=os.getenv("STEAM_LANGUAGE", "english"),
            steam_min_discount_percent=int(os.getenv("STEAM_MIN_DISCOUNT_PERCENT", "60")),
            steam_max_specials=int(os.getenv("STEAM_MAX_SPECIALS", "20")),
            steam_max_new_releases=int(os.getenv("STEAM_MAX_NEW_RELEASES", "10")),
            epic_country=os.getenv("EPIC_COUNTRY", "IN"),
            epic_locale=os.getenv("EPIC_LOCALE", "en-US"),
            epic_max_items=int(os.getenv("EPIC_MAX_ITEMS", "10")),
            max_event_age_days=int(os.getenv("MAX_EVENT_AGE_DAYS", "7")),
            # NVIDIA fallback configuration (optional)
            nvidia_api_key=os.getenv("NVIDIA_API_KEY", ""),
            nvidia_model=os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"),
            nvidia_base_url=os.getenv(
                "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
            ),
            nvidia_timeout_seconds=float(os.getenv("NVIDIA_TIMEOUT_SECONDS", "60")),
        )

    def require_runtime_secrets(self) -> None:
        missing = [
            name
            for name, value in {
                "GEMINI_API_KEY": self.gemini_api_key,
                "EMAIL_ADDRESS": self.email_address,
                "EMAIL_PASSWORD": self.email_password,
                "EMAIL_TO": self.email_to,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required environment variables: {joined}")


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = _clean_env_value(value.strip())
        if key and key not in os.environ:
            os.environ[key] = value


def _clean_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
