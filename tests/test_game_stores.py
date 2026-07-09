from datetime import datetime, timedelta, timezone

from tools.game_stores import EpicGamesStoreTool, SteamStoreTool


def test_steam_store_tool_extracts_deep_special_and_new_release() -> None:
    tool = SteamStoreTool(min_discount_percent=60)
    payload = {
        "specials": {
            "items": [
                {
                    "id": 123,
                    "name": "Great Game",
                    "discount_percent": 75,
                    "final_price": 24900,
                    "original_price": 99900,
                    "currency": "INR",
                },
                {
                    "id": 456,
                    "name": "Small Discount Game",
                    "discount_percent": 20,
                    "final_price": 79900,
                    "original_price": 99900,
                    "currency": "INR",
                },
            ]
        },
        "new_releases": {
            "items": [
                {
                    "id": 789,
                    "name": "New Game",
                    "final_price": 49900,
                    "currency": "INR",
                }
            ]
        },
    }

    events = tool._special_events(payload) + tool._new_release_events(payload)

    assert len(events) == 2
    assert events[0].source == "steam_store"
    assert "75% off" in events[0].title
    assert "Small Discount Game" not in " ".join(event.title for event in events)
    assert "new on Steam" in events[1].title


def test_epic_games_store_tool_extracts_active_free_game() -> None:
    now = datetime.now(timezone.utc)
    tool = EpicGamesStoreTool()
    item = {
        "id": "abc",
        "title": "Free Epic Game",
        "catalogNs": {"mappings": [{"pageSlug": "free-epic-game"}]},
        "promotions": {
            "promotionalOffers": [
                {
                    "promotionalOffers": [
                        {
                            "startDate": (now - timedelta(days=1)).isoformat(),
                            "endDate": (now + timedelta(days=1)).isoformat(),
                            "discountSetting": {
                                "discountType": "PERCENTAGE",
                                "discountPercentage": 0,
                            },
                        }
                    ]
                }
            ]
        },
    }

    event = tool._event_from_item(item)

    assert event is not None
    assert event.source == "epic_games_store"
    assert "free on Epic Games Store" in event.title
    assert "store.epicgames.com" in str(event.url)
