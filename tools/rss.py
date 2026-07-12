from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import sys
from typing import Iterable
from urllib.parse import quote_plus
from xml.etree import ElementTree

from agent.models import Event


@dataclass(frozen=True)
class RssSource:
    name: str
    url: str


class RssTool:
    def __init__(
        self,
        *,
        sources: Iterable[RssSource],
        limit_per_source: int = 5,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.name = "rss"
        self.sources = list(sources)
        self.limit_per_source = limit_per_source
        self.timeout_seconds = timeout_seconds

    def collect(self) -> list[Event]:
        import httpx

        events: list[Event] = []
        for source in self.sources:
            try:
                response = httpx.get(source.url, timeout=self.timeout_seconds)
                response.raise_for_status()
                events.extend(
                    self._events_from_xml(
                        xml=response.text,
                        source_name=source.name,
                    )[: self.limit_per_source]
                )
            except Exception as error:
                print(
                    f"[WARN] RSS source {source.name} failed; continuing: {error}",
                    file=sys.stderr,
                )
        return events

    def _events_from_xml(self, *, xml: str, source_name: str) -> list[Event]:
        root = ElementTree.fromstring(xml)
        items = root.findall("./channel/item")
        events: list[Event] = []

        for item in items:
            title = _child_text(item, "title") or "Untitled RSS item"
            link = _child_text(item, "link") or ""
            guid = _child_text(item, "guid") or link or title
            description = _child_text(item, "description") or ""
            published = _parse_rss_datetime(_child_text(item, "pubDate"))

            events.append(
                Event(
                    id=guid,
                    source=source_name,
                    title=title,
                    summary=_clean_summary(description),
                    url=link,
                    timestamp=published,
                )
            )

        return events


def build_default_bengaluru_sources() -> list[RssSource]:
    return [
        google_news_source(
            name="bengaluru_city_alerts",
            query=(
                'Bengaluru OR Bangalore traffic OR "power cut" OR '
                '"water supply" OR BMTC OR "Namma Metro" OR bandh'
            ),
        ),
        google_news_source(
            name="bengaluru_civic_updates",
            query=(
                'Bengaluru BBMP OR BESCOM OR BWSSB OR "Namma Metro" OR '
                '"Bangalore airport" OR "Bengaluru traffic police"'
            ),
        ),
    ]


def build_default_deal_sources() -> list[RssSource]:
    return [
        google_news_source(
            name="india_ecommerce_sales",
            query=(
                'India sale alert Flipkart OR Amazon OR Myntra OR Ajio '
                'discount OR offer OR "price drop"'
            ),
        ),
        google_news_source(
            name="bengaluru_food_delivery_deals",
            query=(
                'Bengaluru Swiggy OR Zomato coupon OR offer OR discount '
                'OR deal OR festival sale'
            ),
        ),
    ]


def build_default_game_sources() -> list[RssSource]:
    return [
        google_news_source(
            name="steam_game_alerts",
            query=(
                'Steam game sale OR "free game" OR "free weekend" OR '
                '"100% off" OR discount OR "new release"'
            ),
        ),
        google_news_source(
            name="epic_games_alerts",
            query=(
                '"Epic Games Store" "free game" OR giveaway OR sale OR '
                '"mystery game" OR "new release"'
            ),
        ),
        google_news_source(
            name="ea_game_alerts",
            query=(
                '"EA app" OR "Electronic Arts" game sale OR "free game" OR '
                '"free weekend" OR "new release"'
            ),
        ),
        google_news_source(
            name="ubisoft_game_alerts",
            query=(
                '"Ubisoft Store" game sale OR giveaway OR "free weekend" OR '
                '"new release" OR discount'
            ),
        ),
    ]


def google_news_source(*, name: str, query: str) -> RssSource:
    encoded = quote_plus(query)
    return RssSource(
        name=name,
        url=f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en",
    )


def _child_text(item: ElementTree.Element, tag: str) -> str:
    child = item.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _parse_rss_datetime(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _clean_summary(value: str) -> str:
    return " ".join(value.split())
