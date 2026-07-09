from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent.models import Event


class SteamStoreTool:
    name = "steam_store"

    def __init__(
        self,
        *,
        country: str = "IN",
        language: str = "english",
        min_discount_percent: int = 60,
        max_specials: int = 20,
        max_new_releases: int = 10,
        timeout_seconds: float = 10.0,
        api_url: str = "https://store.steampowered.com/api/featuredcategories",
    ) -> None:
        self.country = country
        self.language = language
        self.min_discount_percent = min_discount_percent
        self.max_specials = max_specials
        self.max_new_releases = max_new_releases
        self.timeout_seconds = timeout_seconds
        self.api_url = api_url

    def collect(self) -> list[Event]:
        import httpx

        response = httpx.get(
            self.api_url,
            params={"cc": self.country, "l": self.language},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()

        events: list[Event] = []
        events.extend(self._special_events(payload))
        events.extend(self._new_release_events(payload))
        return events

    def _special_events(self, payload: dict[str, Any]) -> list[Event]:
        items = payload.get("specials", {}).get("items", [])
        events: list[Event] = []

        for item in items:
            discount = int(item.get("discount_percent") or 0)
            final_price = _steam_price(item.get("final_price"), item.get("currency"))
            original_price = _steam_price(item.get("original_price"), item.get("currency"))
            is_free = discount >= 100 or item.get("final_price") == 0

            if not is_free and discount < self.min_discount_percent:
                continue

            app_id = str(item.get("id") or item.get("appid") or item.get("name"))
            title = str(item.get("name") or "Steam deal")
            deal_label = "Free on Steam" if is_free else f"{discount}% off on Steam"
            summary = f"{deal_label}. Current price: {final_price}; original price: {original_price}."

            events.append(
                Event(
                    id=f"steam-special-{app_id}-{discount}-{item.get('final_price')}",
                    source=self.name,
                    title=f"{title} - {deal_label}",
                    summary=summary,
                    url=f"https://store.steampowered.com/app/{app_id}",
                    timestamp=datetime.now(timezone.utc),
                )
            )

        return events[: self.max_specials]

    def _new_release_events(self, payload: dict[str, Any]) -> list[Event]:
        items = payload.get("new_releases", {}).get("items", [])
        events: list[Event] = []

        for item in items[: self.max_new_releases]:
            app_id = str(item.get("id") or item.get("appid") or item.get("name"))
            title = str(item.get("name") or "Steam new release")
            price = _steam_price(item.get("final_price"), item.get("currency"))

            events.append(
                Event(
                    id=f"steam-new-release-{app_id}",
                    source=self.name,
                    title=f"{title} - new on Steam",
                    summary=f"Steam new release. Current price: {price}.",
                    url=f"https://store.steampowered.com/app/{app_id}",
                    timestamp=datetime.now(timezone.utc),
                )
            )

        return events


class EpicGamesStoreTool:
    name = "epic_games_store"

    def __init__(
        self,
        *,
        country: str = "IN",
        locale: str = "en-US",
        max_items: int = 10,
        timeout_seconds: float = 10.0,
        api_url: str = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions",
    ) -> None:
        self.country = country
        self.locale = locale
        self.max_items = max_items
        self.timeout_seconds = timeout_seconds
        self.api_url = api_url

    def collect(self) -> list[Event]:
        import httpx

        response = httpx.get(
            self.api_url,
            params={
                "locale": self.locale,
                "country": self.country,
                "allowCountries": self.country,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        elements = (
            payload.get("data", {})
            .get("Catalog", {})
            .get("searchStore", {})
            .get("elements", [])
        )

        events = [event for item in elements if (event := self._event_from_item(item))]
        return events[: self.max_items]

    def _event_from_item(self, item: dict[str, Any]) -> Event | None:
        if not _has_active_epic_free_offer(item):
            return None

        title = str(item.get("title") or "Epic Games Store free game")
        slug = _epic_slug(item)
        offer_id = str(item.get("id") or item.get("productSlug") or title)
        start, end = _epic_offer_window(item)
        window = ""
        if start and end:
            window = f" Claim window: {start.date().isoformat()} to {end.date().isoformat()}."

        return Event(
            id=f"epic-free-{offer_id}-{end.isoformat() if end else ''}",
            source=self.name,
            title=f"{title} - free on Epic Games Store",
            summary=f"Epic Games Store free-game promotion is currently active.{window}",
            url=f"https://store.epicgames.com/p/{slug}" if slug else "https://store.epicgames.com/free-games",
            timestamp=start or datetime.now(timezone.utc),
        )


def _steam_price(value: Any, currency: Any) -> str:
    if value is None:
        return "unknown"
    amount = int(value) / 100
    if amount == 0:
        return "free"
    return f"{currency or ''} {amount:.2f}".strip()


def _has_active_epic_free_offer(item: dict[str, Any]) -> bool:
    now = datetime.now(timezone.utc)
    promotions = item.get("promotions") or {}
    promotional_offers = promotions.get("promotionalOffers") or []

    for group in promotional_offers:
        for offer in group.get("promotionalOffers", []):
            start = _parse_epic_datetime(offer.get("startDate"))
            end = _parse_epic_datetime(offer.get("endDate"))
            discount = offer.get("discountSetting", {})
            if (
                discount.get("discountType") == "PERCENTAGE"
                and int(discount.get("discountPercentage") or 0) == 0
                and start
                and end
                and start <= now <= end
            ):
                return True

    price = item.get("price", {}).get("totalPrice", {})
    return price.get("discountPrice") == 0 and price.get("originalPrice", 1) != 0


def _epic_offer_window(item: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    promotions = item.get("promotions") or {}
    promotional_offers = promotions.get("promotionalOffers") or []
    for group in promotional_offers:
        for offer in group.get("promotionalOffers", []):
            return (
                _parse_epic_datetime(offer.get("startDate")),
                _parse_epic_datetime(offer.get("endDate")),
            )
    return None, None


def _parse_epic_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _epic_slug(item: dict[str, Any]) -> str:
    mappings = item.get("catalogNs", {}).get("mappings") or []
    if mappings and mappings[0].get("pageSlug"):
        return str(mappings[0]["pageSlug"])
    if item.get("productSlug"):
        return str(item["productSlug"])
    return ""
