from datetime import date

import requests

import news_service
from news_service import fetch_current_affairs, parse_feed


def make_feed(items):
    entries = []
    for title, published, description, link in items:
        entries.append(
            "<item>"
            f"<title>{title}</title><link>{link}</link>"
            f"<pubDate>{published}</pubDate><description><![CDATA[{description}]]></description>"
            "</item>"
        )
    return ("<rss><channel>" + "".join(entries) + "</channel></rss>").encode()


def test_rss_parser_sanitizes_text_and_matches_india_local_date():
    feed = {"source": "Test Wire", "category": "national"}
    xml = make_feed(
        [
            (
                "India policy update",
                "Thu, 29 Oct 2026 20:00:00 GMT",
                "<p>New <b>policy</b> details</p>",
                "https://example.org/story",
            ),
            (
                "Older report",
                "Thu, 29 Oct 2026 18:00:00 GMT",
                "Not on the requested India date",
                "https://example.org/older",
            ),
        ]
    )
    articles = parse_feed(xml, feed, date(2026, 10, 30))
    assert len(articles) == 1
    assert articles[0]["title"] == "India policy update"
    assert articles[0]["description"] == "New policy details"
    assert articles[0]["source"] == "Test Wire"


def test_explicit_date_and_both_categories_are_grouped(monkeypatch):
    def fake_get(url, **kwargs):
        if "world/rss" in url:
            title = "Global summit opens"
        elif "international/feeder" in url:
            title = "International climate talks"
        elif "india/rss" in url:
            title = "India parliament session"
        else:
            title = "National budget update"
        return type(
            "Response",
            (),
            {
                "content": make_feed(
                    [(title, "Fri, 30 Oct 2026 06:00:00 GMT", "A current affairs report", "https://example.org/news")]
                ),
                "raise_for_status": lambda self: None,
            },
        )()

    monkeypatch.setattr(news_service.requests, "get", fake_get)
    result, status = fetch_current_affairs(
        "30 October 2026 current affairs international and national India",
        today=date(2026, 10, 30),
    )
    assert status == 200
    assert result["date"] == "2026-10-30"
    assert [category["key"] for category in result["categories"]] == ["international", "national"]
    assert result["total"] == 4
    assert all(category["articles"] for category in result["categories"])


def test_news_topic_filters_headlines(monkeypatch):
    def fake_get(url, **kwargs):
        return type(
            "Response",
            (),
            {
                "content": make_feed(
                    [
                        ("India election results", "Fri, 30 Oct 2026 06:00:00 GMT", "Election update", "https://example.org/election"),
                        ("India sports final", "Fri, 30 Oct 2026 06:00:00 GMT", "Sports update", "https://example.org/sports"),
                    ]
                ),
                "raise_for_status": lambda self: None,
            },
        )()

    monkeypatch.setattr(news_service.requests, "get", fake_get)
    result, status = fetch_current_affairs("news election", today=date(2026, 10, 30))
    assert status == 200
    articles = [article for category in result["categories"] for article in category["articles"]]
    assert result["total"] == 4
    assert all("election" in article["title"].lower() for article in articles)


def test_bad_date_and_unavailable_feeds_return_clear_errors(monkeypatch):
    result, status = fetch_current_affairs("current affairs", date_override="not-a-date")
    assert status == 400
    assert "YYYY-MM-DD" in result["message"]

    def offline(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(news_service.requests, "get", offline)
    result, status = fetch_current_affairs("today current affairs", today=date(2026, 10, 30))
    assert status == 502
    assert "could not be reached" in result["message"].lower()


def test_partial_feed_failure_is_reported_with_successful_results(monkeypatch):
    def partly_available(url, **kwargs):
        if "thehindu.com" in url:
            raise requests.ConnectionError("offline source")
        return type(
            "Response",
            (),
            {
                "content": make_feed(
                    [("World update", "Fri, 30 Oct 2026 06:00:00 GMT", "A report", "https://example.org/world")]
                ),
                "raise_for_status": lambda self: None,
            },
        )()

    monkeypatch.setattr(news_service.requests, "get", partly_available)
    result, status = fetch_current_affairs("today international", today=date(2026, 10, 30))
    assert status == 200
    assert result["total"] == 1
    assert "some news sources could not be reached" in result["message"].lower()