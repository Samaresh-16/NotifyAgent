from tools.rss import (
    RssTool,
    build_default_bengaluru_sources,
    build_default_deal_sources,
    build_default_game_sources,
)


def test_rss_tool_parses_items() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Bengaluru rain alert</title>
      <link>https://example.com/rain</link>
      <guid>rain-1</guid>
      <description>Heavy showers expected in east Bengaluru.</description>
      <pubDate>Sat, 27 Jun 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
    tool = RssTool(sources=[])

    events = tool._events_from_xml(xml=xml, source_name="test_source")

    assert len(events) == 1
    assert events[0].source == "test_source"
    assert events[0].title == "Bengaluru rain alert"
    assert events[0].url == "https://example.com/rain"


def test_default_sources_are_bengaluru_and_deal_focused() -> None:
    sources = build_default_bengaluru_sources() + build_default_deal_sources()
    names = {source.name for source in sources}

    assert "bengaluru_city_alerts" in names
    assert "india_ecommerce_sales" in names
    assert all("news.google.com/rss/search" in source.url for source in sources)
    assert all("rain" not in source.url.lower() for source in sources)


def test_default_game_sources_cover_requested_platforms() -> None:
    sources = build_default_game_sources()
    urls = " ".join(source.url.lower() for source in sources)
    names = {source.name for source in sources}

    assert names == {
        "steam_game_alerts",
        "epic_games_alerts",
        "ea_game_alerts",
        "ubisoft_game_alerts",
    }
    assert "steam" in urls
    assert "epic" in urls
    assert "electronic+arts" in urls
    assert "ubisoft" in urls
