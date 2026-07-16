"""News retrieval layer"""
from enum import unique
import time
import hashlib
import logging
from datetime import datetime, timezone
from time import mktime
from typing import Optional

import requests
import feedparser

from models import NewsArticle
from database import store_articles
from config import settings

logger = logging.getLogger(__name__)

# Global state for Finnhub development rate limiter
_last_finnhub_call_time = 0.0


def _enforce_finnhub_rate_limit() -> None:
    """
    Sleeps the thread if consecutive Finnhub requests are made too quickly.
    """
    global _last_finnhub_call_time
    elapsed = time.time() - _last_finnhub_call_time
    if elapsed < settings.finnhub_request_delay:
        time.sleep(settings.finnhub_request_delay - elapsed)
    _last_finnhub_call_time = time.time()


def _generate_hash(title: str, url: str) -> str:
    """Computes a SHA256 hash based on article title and URL."""
    payload = f"{title}{url}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _extract_rss_content(entry: dict) -> str:
    """
    Attempts to extract the full article body from an RSS entry.
    Prefers 'content:encoded' (mapped to entry.content by feedparser).
    """
    if "content" in entry and isinstance(entry.content, list) and len(entry.content) > 0:
        return entry.content[0].get("value", "").strip()
    return ""


def _collect_rss_feed(url: str, source_name: str, limit: Optional[int] = None) -> list[NewsArticle]:
    """Generic helper to fetch and normalize articles from any RSS feed."""
    articles = []

    try:
        feed = feedparser.parse(url)
        if feed.bozo and feed.bozo_exception:
            logger.warning(f"Malformed RSS feed from {source_name}: {feed.bozo_exception}")
            # We continue because feedparser often recovers partial data despite bozo flag
    except Exception as e:
        logger.error(f"Failed to fetch RSS from {source_name}: {e}")
        return []

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()

        if not title or not link:
            continue

        if "published_parsed" in entry and entry.published_parsed:
            published_at = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc)
        else:
            published_at = datetime.now(timezone.utc)

        articles.append(NewsArticle(
            source=source_name,
            external_id=entry.get("id", link),
            title=title,
            summary=entry.get("summary", ""),
            content=_extract_rss_content(entry),
            url=link,
            published_at=published_at,
            hash=_generate_hash(title, link)
        ))

        if limit and len(articles) >= limit:
            break

    return articles


def collect_marketwatch_news(limit: Optional[int] = None) -> list[NewsArticle]:
    """Fetches and normalizes articles from the MarketWatch RSS feed."""
    return _collect_rss_feed(settings.marketwatch_rss_url, "MarketWatch", limit)


def collect_yahoo_news(limit: Optional[int] = None) -> list[NewsArticle]:
    """Fetches and normalizes articles from the Yahoo Finance RSS feed."""
    return _collect_rss_feed(settings.yahoo_finance_rss_url, "Yahoo Finance", limit)


def collect_finnhub_news(limit: Optional[int] = None) -> list[NewsArticle]:
    """Fetches and normalizes articles from the Finnhub General News API."""
    _enforce_finnhub_rate_limit()

    url = f"https://finnhub.io/api/v1/news?category=general&token={settings.finnhub_api_key}"

    try:
        response = requests.get(url, timeout=10)    
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch Finnhub news: {e}")
        return []

    articles = []
    for item in data:
        title = item.get("headline", "").strip()
        url = item.get("url", "").strip()

        if not title or not url:
            continue

        # Finnhub provides timestamps in UNIX epoch seconds
        timestamp = item.get("datetime", time.time())
        published_at = datetime.fromtimestamp(timestamp, timezone.utc)

        articles.append(NewsArticle(
            source="Finnhub",
            external_id=str(item.get("id", "")),
            title=title,
            summary=item.get("summary", ""),
            content="",
            url=url,
            published_at=published_at,
            hash=_generate_hash(title, url)
        ))

        if limit and len(articles) >= limit:
            break

    return articles


def collect_news(limit_per_source: Optional[int] = None) -> tuple[list[NewsArticle], int, int]:
    """
    Orchestrator function:
    1. Collects raw news from all configured sources.
    2. Discards duplicates based on SHA256 hashes (title + url).
    3. Persists new articles to the database.
    4. Returns a tuple (list of unique articles, number of inserted, and skipped articles)
    """
    raw_articles = []

    # 1. Fetch from all sources
    raw_articles.extend(collect_marketwatch_news(limit=limit_per_source))
    raw_articles.extend(collect_yahoo_news(limit=limit_per_source))
    raw_articles.extend(collect_finnhub_news(limit=limit_per_source))

    # 2. In-memory Deduplication (Keep the first seen)
    unique_articles = []
    seen_hashes = set()

    for article in raw_articles:
        if article.hash not in seen_hashes:
            unique_articles.append(article)
            seen_hashes.add(article.hash)

    duplicates_removed = len(raw_articles) - len(unique_articles)
    logger.info(f"Removed {duplicates_removed} in-memory duplicates")

    inserted = 0
    skipped = 0

    # 3. Store to Database
    try:
        inserted = store_articles(unique_articles)
        skipped = len(unique_articles) - inserted
        logger.info(f"DB Insertion: {inserted} inserted, {skipped} skipped (already exist).")
    except Exception as e:
        logger.error(f"Database inserion failed: {e}")

    # 4. Return deduplicated_list
    return unique_articles, inserted, skipped