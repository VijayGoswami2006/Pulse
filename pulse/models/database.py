"""
Database module for PULSE.
Handles all SQLite operations using raw sqlite3 (no ORM) for simplicity.
"""

import sqlite3
import json
from datetime import datetime
from config import Config


def get_db():
    """Return a database connection with row_factory set to sqlite3.Row."""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they do not already exist."""
    conn = get_db()
    cursor = conn.cursor()

    # ── Articles ──────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            summary     TEXT,
            content     TEXT,
            url         TEXT    UNIQUE,
            source      TEXT,
            category    TEXT    DEFAULT 'General',
            author      TEXT,
            published   TEXT,
            image_url   TEXT,
            tags        TEXT    DEFAULT '[]',
            relevance_score REAL DEFAULT 0.0,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Saved Ideas ───────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ideas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT,
            raw_text        TEXT    NOT NULL,
            refined_text    TEXT,
            suggested_titles TEXT   DEFAULT '[]',
            outline         TEXT,
            tone            TEXT    DEFAULT 'professional',
            keywords        TEXT    DEFAULT '[]',
            image_path      TEXT,
            status          TEXT    DEFAULT 'draft',
            created_at      TEXT    DEFAULT (datetime('now')),
            updated_at      TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Blog Drafts ───────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blog_drafts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            content     TEXT    DEFAULT '',
            outline     TEXT    DEFAULT '[]',
            tone        TEXT    DEFAULT 'professional',
            keywords    TEXT    DEFAULT '[]',
            status      TEXT    DEFAULT 'draft',
            word_count  INTEGER DEFAULT 0,
            idea_id     INTEGER,
            created_at  TEXT    DEFAULT (datetime('now')),
            updated_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (idea_id) REFERENCES ideas(id) ON DELETE SET NULL
        )
    """)

    # ── Saved AI Suggestions ──────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_suggestions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            topic           TEXT    NOT NULL,
            explanation     TEXT,
            suggested_titles TEXT   DEFAULT '[]',
            keywords        TEXT    DEFAULT '[]',
            content_angle   TEXT,
            source_articles TEXT    DEFAULT '[]',
            created_at      TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Topic Trends ──────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topic_trends (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            topic           TEXT    NOT NULL,
            mention_count   INTEGER DEFAULT 1,
            score           REAL    DEFAULT 0.0,
            category        TEXT    DEFAULT 'General',
            hashtags        TEXT    DEFAULT '[]',
            last_seen       TEXT    DEFAULT (datetime('now')),
            created_at      TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── User Settings ─────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Custom RSS Feeds ──────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_feeds (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            url         TEXT    NOT NULL UNIQUE,
            category    TEXT    DEFAULT 'General',
            active      INTEGER DEFAULT 1,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    print("[OK] Database initialised.")


# ── Helper utilities ──────────────────────────────────────────────────────────

def row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    """Convert a list of sqlite3.Row objects to a list of dicts."""
    return [dict(r) for r in rows]


# ── Articles ──────────────────────────────────────────────────────────────────

def insert_article(article: dict) -> int | None:
    """Insert an article; return new id or None if duplicate URL."""
    conn = get_db()
    try:
        tags = json.dumps(article.get("tags", []))
        cur = conn.execute("""
            INSERT OR IGNORE INTO articles
                (title, summary, content, url, source, category, author, published, image_url, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            article.get("title", "Untitled"),
            article.get("summary", ""),
            article.get("content", ""),
            article.get("url", ""),
            article.get("source", "Unknown"),
            article.get("category", "General"),
            article.get("author", ""),
            article.get("published", ""),
            article.get("image_url", ""),
            tags,
        ))
        conn.commit()
        return cur.lastrowid if cur.rowcount else None
    finally:
        conn.close()


def get_articles(search: str = "", category: str = "", limit: int = 100, offset: int = 0):
    conn = get_db()
    try:
        query = "SELECT * FROM articles WHERE 1=1"
        params = []
        if search:
            query += " AND (title LIKE ? OR summary LIKE ? OR source LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


def get_article_count():
    conn = get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    finally:
        conn.close()


def get_articles_by_ids(ids: list):
    conn = get_db()
    try:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM articles WHERE id IN ({placeholders})", ids
        ).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


# ── Ideas ─────────────────────────────────────────────────────────────────────

def save_idea(idea: dict) -> int:
    conn = get_db()
    try:
        cur = conn.execute("""
            INSERT INTO ideas (title, raw_text, refined_text, suggested_titles, outline, tone, keywords, image_path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            idea.get("title", ""),
            idea.get("raw_text", ""),
            idea.get("refined_text", ""),
            json.dumps(idea.get("suggested_titles", [])),
            idea.get("outline", ""),
            idea.get("tone", "professional"),
            json.dumps(idea.get("keywords", [])),
            idea.get("image_path", ""),
            idea.get("status", "draft"),
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_idea(idea_id: int, updates: dict):
    conn = get_db()
    try:
        # Serialise list fields
        for field in ("suggested_titles", "keywords"):
            if field in updates and isinstance(updates[field], list):
                updates[field] = json.dumps(updates[field])
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [idea_id]
        conn.execute(f"UPDATE ideas SET {set_clause} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def get_ideas(limit: int = 50):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM ideas ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


def get_idea(idea_id: int):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def delete_idea(idea_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
        conn.commit()
    finally:
        conn.close()


# ── Blog Drafts ───────────────────────────────────────────────────────────────

def save_draft(draft: dict) -> int:
    conn = get_db()
    try:
        content = draft.get("content", "")
        word_count = len(content.split()) if content else 0
        cur = conn.execute("""
            INSERT INTO blog_drafts (title, content, outline, tone, keywords, status, word_count, idea_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            draft.get("title", "Untitled"),
            content,
            json.dumps(draft.get("outline", [])),
            draft.get("tone", "professional"),
            json.dumps(draft.get("keywords", [])),
            draft.get("status", "draft"),
            word_count,
            draft.get("idea_id"),
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_draft(draft_id: int, updates: dict):
    conn = get_db()
    try:
        for field in ("outline", "keywords"):
            if field in updates and isinstance(updates[field], list):
                updates[field] = json.dumps(updates[field])
        if "content" in updates:
            updates["word_count"] = len(updates["content"].split())
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [draft_id]
        conn.execute(f"UPDATE blog_drafts SET {set_clause} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def get_drafts(limit: int = 50):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM blog_drafts ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


def get_draft(draft_id: int):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM blog_drafts WHERE id = ?", (draft_id,)).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def delete_draft(draft_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM blog_drafts WHERE id = ?", (draft_id,))
        conn.commit()
    finally:
        conn.close()


# ── Saved Suggestions ─────────────────────────────────────────────────────────

def save_suggestion(suggestion: dict) -> int:
    conn = get_db()
    try:
        cur = conn.execute("""
            INSERT INTO saved_suggestions (topic, explanation, suggested_titles, keywords, content_angle, source_articles)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            suggestion.get("topic", ""),
            suggestion.get("explanation", ""),
            json.dumps(suggestion.get("suggested_titles", [])),
            json.dumps(suggestion.get("keywords", [])),
            suggestion.get("content_angle", ""),
            json.dumps(suggestion.get("source_articles", [])),
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_saved_suggestions(limit: int = 50):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM saved_suggestions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


def delete_suggestion(suggestion_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM saved_suggestions WHERE id = ?", (suggestion_id,))
        conn.commit()
    finally:
        conn.close()


# ── Topic Trends ──────────────────────────────────────────────────────────────

def upsert_topic_trend(topic: str, category: str = "General", score_delta: float = 1.0):
    conn = get_db()
    try:
        existing = conn.execute("SELECT id, mention_count, score FROM topic_trends WHERE topic = ?", (topic,)).fetchone()
        now = datetime.utcnow().isoformat()
        if existing:
            conn.execute(
                "UPDATE topic_trends SET mention_count = mention_count + 1, score = ?, last_seen = ? WHERE id = ?",
                (existing["score"] + score_delta, now, existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO topic_trends (topic, category, score, last_seen) VALUES (?, ?, ?, ?)",
                (topic, category, score_delta, now)
            )
        conn.commit()
    finally:
        conn.close()


def get_trending_topics(limit: int = 10):
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT * FROM topic_trends
            ORDER BY score DESC, mention_count DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


# ── Settings ──────────────────────────────────────────────────────────────────

def get_setting(key: str, default=None):
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str):
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, value))
        conn.commit()
    finally:
        conn.close()


def get_all_settings():
    conn = get_db()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        conn.close()


# ── Custom Feeds ──────────────────────────────────────────────────────────────

def add_custom_feed(name: str, url: str, category: str = "General") -> int:
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO custom_feeds (name, url, category) VALUES (?, ?, ?)",
            (name, url, category)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_custom_feeds():
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM custom_feeds WHERE active = 1").fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


def delete_custom_feed(feed_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM custom_feeds WHERE id = ?", (feed_id,))
        conn.commit()
    finally:
        conn.close()


# ── Dashboard stats ───────────────────────────────────────────────────────────

def get_dashboard_stats():
    conn = get_db()
    try:
        article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        idea_count = conn.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
        draft_count = conn.execute("SELECT COUNT(*) FROM blog_drafts").fetchone()[0]
        suggestion_count = conn.execute("SELECT COUNT(*) FROM saved_suggestions").fetchone()[0]

        # Category distribution
        cat_rows = conn.execute("""
            SELECT category, COUNT(*) as cnt FROM articles
            GROUP BY category ORDER BY cnt DESC LIMIT 8
        """).fetchall()
        category_dist = [{"category": r["category"], "count": r["cnt"]} for r in cat_rows]

        # Recent drafts
        recent_drafts = conn.execute("""
            SELECT id, title, status, word_count, updated_at
            FROM blog_drafts ORDER BY updated_at DESC LIMIT 5
        """).fetchall()

        # Trending topics
        trends = conn.execute("""
            SELECT topic, score, mention_count, category
            FROM topic_trends ORDER BY score DESC LIMIT 8
        """).fetchall()

        return {
            "article_count": article_count,
            "idea_count": idea_count,
            "draft_count": draft_count,
            "suggestion_count": suggestion_count,
            "category_distribution": category_dist,
            "recent_drafts": rows_to_list(recent_drafts),
            "trending_topics": rows_to_list(trends),
        }
    finally:
        conn.close()
