"""
news_service.py — Fetches content from RSS feeds and arXiv.
Deduplication is handled by the unique URL constraint in SQLite.
"""

import feedparser
import requests
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from bs4 import BeautifulSoup
from config import Config
from models.database import insert_article, get_custom_feeds


# ── Utilities ─────────────────────────────────────────────────────────────────

def _clean_html(html: str) -> str:
    """Strip HTML tags, return plain text limited to ~500 chars."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ", strip=True)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:500]


def _parse_date(entry) -> str:
    """Return ISO date string from feedparser entry or today."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6]).isoformat()
        except Exception:
            pass
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6]).isoformat()
        except Exception:
            pass
    return datetime.utcnow().isoformat()


def _extract_image(entry) -> str:
    """Try to find a thumbnail / image from the RSS entry."""
    # media:thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url", "")
    # media:content
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            if m.get("type", "").startswith("image"):
                return m.get("url", "")
    # enclosure
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href", "")
    return ""


# ── RSS Feeds ─────────────────────────────────────────────────────────────────

def fetch_rss_feed(feed_url: str, source_name: str, category: str = "General") -> int:
    """
    Fetch a single RSS feed.
    Returns the number of new articles inserted.
    """
    try:
        # feedparser handles HTTP internally; set a timeout via requests instead
        resp = requests.get(feed_url, timeout=12, headers={"User-Agent": "PULSE/1.0"})
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as e:
        print(f"[WARN] Could not fetch {feed_url}: {e}")
        return 0

    new_count = 0
    entries = feed.entries[: Config.MAX_ARTICLES_PER_FEED]

    for entry in entries:
        title = getattr(entry, "title", "").strip()
        link  = getattr(entry, "link", "").strip()

        if not title or not link:
            continue

        # Summary / content
        summary = ""
        if hasattr(entry, "summary"):
            summary = _clean_html(entry.summary)
        elif hasattr(entry, "content") and entry.content:
            summary = _clean_html(entry.content[0].get("value", ""))

        article = {
            "title":     title,
            "summary":   summary,
            "url":       link,
            "source":    source_name,
            "category":  category,
            "author":    getattr(entry, "author", ""),
            "published": _parse_date(entry),
            "image_url": _extract_image(entry),
            "tags":      [t.term for t in getattr(entry, "tags", []) if hasattr(t, "term")][:5],
        }

        inserted = insert_article(article)
        if inserted:
            new_count += 1

    return new_count


def fetch_all_feeds() -> dict:
    """
    Fetch all built-in + custom RSS feeds.
    Returns {"new_articles": int, "feeds_fetched": int, "errors": list}
    """
    total_new = 0
    errors = []

    all_feeds = list(Config.RSS_FEEDS)

    # Add user-added custom feeds
    try:
        custom = get_custom_feeds()
        for f in custom:
            all_feeds.append({"name": f["name"], "url": f["url"], "category": f["category"]})
    except Exception as e:
        print(f"Could not load custom feeds: {e}")

    for feed in all_feeds:
        try:
            new = fetch_rss_feed(feed["url"], feed["name"], feed.get("category", "General"))
            total_new += new
            print(f"  [OK] {feed['name']}: {new} new articles")
        except Exception as e:
            errors.append(f"{feed['name']}: {e}")
            print(f"  [ERR] {feed['name']}: {e}")

    return {"new_articles": total_new, "feeds_fetched": len(all_feeds), "errors": errors}


# ── arXiv ─────────────────────────────────────────────────────────────────────

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_NS = {
    "atom":    "http://www.w3.org/2005/Atom",
    "arxiv":   "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


def fetch_arxiv(query: str, category: str = "cs.AI") -> dict:
    """
    Search arXiv for papers matching `query` in the given category.
    Returns {"new_articles": int, "total_found": int}
    """
    search_q = f"cat:{category}+AND+all:{query.replace(' ', '+')}"
    params = {
        "search_query": search_q,
        "max_results": Config.ARXIV_MAX_RESULTS,
        "sortBy": "lastUpdatedDate",
        "sortOrder": "descending",
    }

    try:
        resp = requests.get(ARXIV_API, params=params, timeout=15,
                            headers={"User-Agent": "PULSE/1.0"})
        resp.raise_for_status()
    except Exception as e:
        print(f"[WARN] arXiv fetch failed: {e}")
        return {"new_articles": 0, "total_found": 0, "error": str(e)}

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        return {"new_articles": 0, "total_found": 0, "error": str(e)}

    total = int(root.findtext("opensearch:totalResults", "0", ARXIV_NS))
    entries = root.findall("atom:entry", ARXIV_NS)
    new_count = 0

    for entry in entries:
        title = (entry.findtext("atom:title", "", ARXIV_NS) or "").replace("\n", " ").strip()
        abstract = (entry.findtext("atom:summary", "", ARXIV_NS) or "").replace("\n", " ").strip()
        url = ""

        for link in entry.findall("atom:link", ARXIV_NS):
            if link.get("rel") == "alternate":
                url = link.get("href", "")
                break
        if not url:
            id_text = entry.findtext("atom:id", "", ARXIV_NS)
            url = id_text.strip() if id_text else ""

        if not title or not url:
            continue

        # Published date
        pub_raw = entry.findtext("atom:published", "", ARXIV_NS)
        try:
            published = datetime.fromisoformat(pub_raw.replace("Z", "+00:00")).isoformat()
        except Exception:
            published = datetime.utcnow().isoformat()

        # Authors
        authors = []
        for author in entry.findall("atom:author", ARXIV_NS):
            name = author.findtext("atom:name", "", ARXIV_NS)
            if name:
                authors.append(name)

        article = {
            "title":    title,
            "summary":  abstract[:500],
            "url":      url,
            "source":   "arXiv",
            "category": "Research",
            "author":   ", ".join(authors[:3]),
            "published": published,
            "image_url": "",
            "tags":     [category],
        }

        inserted = insert_article(article)
        if inserted:
            new_count += 1

    return {"new_articles": new_count, "total_found": total}


# ── URL scraper ───────────────────────────────────────────────────────────────

def fetch_url_content(url: str) -> dict:
    """
    Scrape article title and text from a URL.
    Returns a partial article dict.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PULSE/1.0)",
            "Accept": "text/html",
        }
        resp = requests.get(url, timeout=12, headers=headers)
        resp.raise_for_status()
    except Exception as e:
        return {"error": str(e)}

    soup = BeautifulSoup(resp.text, "lxml")

    # Title
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title:
        title = og_title.get("content", "")
    if not title:
        title = soup.find("title")
        title = title.get_text().strip() if title else ""

    # Description / summary
    desc = ""
    og_desc = soup.find("meta", property="og:description")
    if og_desc:
        desc = og_desc.get("content", "")
    if not desc:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            desc = meta_desc.get("content", "")

    # Main text fallback
    if not desc:
        article_tag = soup.find("article") or soup.find("main") or soup.find("body")
        if article_tag:
            desc = article_tag.get_text(separator=" ", strip=True)[:500]

    # Image
    image_url = ""
    og_img = soup.find("meta", property="og:image")
    if og_img:
        image_url = og_img.get("content", "")

    return {
        "title":     title[:200],
        "summary":   desc[:500],
        "url":       url,
        "image_url": image_url,
    }
