import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

FEEDS = (
    {
        "category": "international",
        "source": "BBC World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
    },
    {
        "category": "international",
        "source": "The Hindu International",
        "url": "https://www.thehindu.com/news/international/feeder/default.rss",
    },
    {
        "category": "national",
        "source": "BBC India",
        "url": "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml",
    },
    {
        "category": "national",
        "source": "The Hindu National",
        "url": "https://www.thehindu.com/news/national/feeder/default.rss",
    },
)
FEED_TIMEOUT_SECONDS = 5
MAX_FEED_BYTES = 2_000_000
INDIA_TIMEZONE = timezone(timedelta(hours=5, minutes=30))
DATE_PATTERN = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})\b"
)
IGNORED_QUERY_WORDS = {
    "affair", "affairs", "and", "are", "current", "give", "global", "india",
    "indian", "international", "latest", "list", "me", "national", "news", "on",
    "please", "today", "what", "world", "yesterday", "the", "for", "of",
}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        cleaned = data.strip()
        if cleaned:
            self.parts.append(cleaned)


def _plain_text(value):
    parser = _TextExtractor()
    parser.feed(value or "")
    return " ".join(parser.parts).strip()


def _tag_name(element):
    return element.tag.rsplit("}", 1)[-1].lower()


def _child_text(element, names):
    for child in element:
        if _tag_name(child) in names:
            return " ".join(child.itertext()).strip()
    return ""


def _item_link(element):
    for child in element:
        if _tag_name(child) != "link":
            continue
        link = child.attrib.get("href") or (child.text or "").strip()
        if urlparse(link).scheme in {"http", "https"}:
            return link
    return ""


def _parse_published(value):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.removesuffix("Z"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_feed(xml_content, feed, target_date):
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return []

    entries = [element for element in root.iter() if _tag_name(element) in {"item", "entry"}]
    articles = []
    for entry in entries:
        title = _plain_text(_child_text(entry, {"title"}))
        published = _parse_published(
            _child_text(entry, {"pubdate", "published", "updated", "date"})
        )
        published_in_india = published.astimezone(INDIA_TIMEZONE) if published else None
        if not title or not published_in_india or published_in_india.date() != target_date:
            continue

        description = _plain_text(
            _child_text(entry, {"description", "summary", "encoded", "content"})
        )
        articles.append(
            {
                "title": title,
                "description": description,
                "source": feed["source"],
                "category": feed["category"],
                "published_at": published.isoformat(),
                "url": _item_link(entry),
            }
        )
    return articles


def _parse_requested_date(query, override=None, today=None):
    if override:
        try:
            return date.fromisoformat(str(override)), None
        except ValueError:
            return None, "Date must use YYYY-MM-DD format."

    lowered = query.lower()
    reference = today or datetime.now(INDIA_TIMEZONE).date()
    if re.search(r"\btoday\b", lowered):
        return reference, None
    if re.search(r"\byesterday\b", lowered):
        return reference.fromordinal(reference.toordinal() - 1), None

    match = DATE_PATTERN.search(query)
    if not match:
        return reference, None

    raw_date = match.group(0)
    for pattern in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
        try:
            return datetime.strptime(raw_date, pattern).date(), None
        except ValueError:
            continue
    return None, f"I couldn't read the date '{raw_date}'. Try YYYY-MM-DD."


def _requested_categories(query):
    lowered = query.lower()
    categories = []
    if any(word in lowered.split() for word in ("international", "world", "global")):
        categories.append("international")
    if any(word in lowered.split() for word in ("national", "india", "indian", "domestic")):
        categories.append("national")
    return categories or ["international", "national"]


def _query_keywords(query):
    without_date = DATE_PATTERN.sub(" ", query.lower())
    return [
        word for word in re.findall(r"[a-z0-9]+", without_date)
        if word not in IGNORED_QUERY_WORDS and len(word) > 1
    ]


def _fetch_feed(feed, target_date):
    try:
        response = requests.get(
            feed["url"],
            timeout=FEED_TIMEOUT_SECONDS,
            headers={"User-Agent": "KAREN-CurrentAffairs/1.0"},
        )
        response.raise_for_status()
        if len(response.content) > MAX_FEED_BYTES:
            return [], {"source": feed["source"], "status": "feed_too_large"}
        return parse_feed(response.content, feed, target_date), {
            "source": feed["source"],
            "status": "ok",
        }
    except requests.RequestException as error:
        return [], {"source": feed["source"], "status": "unavailable", "message": str(error)}


def fetch_current_affairs(query, date_override=None, today=None):
    target_date, date_error = _parse_requested_date(query, date_override, today)
    if date_error:
        return {"error": True, "message": date_error}, 400

    categories = _requested_categories(query)
    keywords = _query_keywords(query)
    selected_feeds = [feed for feed in FEEDS if feed["category"] in categories]
    articles = []
    feed_statuses = []
    with ThreadPoolExecutor(max_workers=len(selected_feeds)) as executor:
        jobs = [executor.submit(_fetch_feed, feed, target_date) for feed in selected_feeds]
        for job in as_completed(jobs):
            feed_articles, status = job.result()
            articles.extend(feed_articles)
            feed_statuses.append(status)

    if keywords:
        articles = [
            article for article in articles
            if any(
                keyword in f"{article['title']} {article['description']}".lower()
                for keyword in keywords
            )
        ]

    articles.sort(key=lambda item: item["published_at"], reverse=True)
    grouped = []
    labels = {"international": "International", "national": "National · India"}
    for category in categories:
        category_articles = [item for item in articles if item["category"] == category]
        grouped.append(
            {"key": category, "label": labels[category], "articles": category_articles[:8]}
        )

    feeds_reachable = any(status["status"] == "ok" for status in feed_statuses)
    message = ""
    unavailable_sources = [
        status["source"] for status in feed_statuses if status["status"] != "ok"
    ]
    if not feeds_reachable:
        message = "News feeds could not be reached. Check the server's internet connection and try again."
    elif not articles:
        message = (
            f"No matching feed stories were published on {target_date.isoformat()}. "
            "Public feeds only retain recent articles, so older dates may not be available."
        )
    elif unavailable_sources:
        message = (
            "Some news sources could not be reached: "
            + ", ".join(unavailable_sources)
            + ". These results may be incomplete."
        )

    summary = f"Current affairs for {target_date.strftime('%d %B %Y')}. "
    if articles:
        summary += f"Found {len(articles)} headline(s)."
    else:
        summary += message

    return {
        "date": target_date.isoformat(),
        "date_label": target_date.strftime("%A, %d %B %Y"),
        "categories": grouped,
        "total": len(articles),
        "message": message,
        "summary": summary,
        "feeds": feed_statuses,
    }, 200 if feeds_reachable else 502