"""
content_analyzer.py — Extracts topics and updates trend scores.
Uses simple frequency counting — no fake engagement stats.
"""

import re
import json
from collections import Counter
from datetime import datetime, timedelta
from models.database import get_articles, upsert_topic_trend, get_trending_topics


# ── Stop words (common words to ignore) ───────────────────────────────────────
STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "but",
    "is", "are", "was", "were", "be", "been", "has", "have", "had", "do", "does",
    "did", "will", "would", "could", "should", "may", "might", "must", "can",
    "this", "that", "these", "those", "it", "its", "with", "from", "by", "as",
    "not", "no", "nor", "so", "yet", "both", "either", "neither", "each",
    "more", "most", "other", "some", "such", "how", "what", "when", "where",
    "why", "who", "which", "than", "then", "than", "also", "into", "over",
    "after", "before", "about", "between", "through", "during", "about",
    "new", "use", "using", "used", "get", "getting", "make", "making",
    "says", "said", "say", "i", "we", "you", "he", "she", "they", "them",
    "their", "our", "your", "my", "his", "her", "just", "like", "here",
    "there", "up", "out", "if", "while", "all", "any", "few", "own",
}

# High-value tech/content keywords that boost score when found
BOOST_KEYWORDS = {
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "llm", "gpt", "chatgpt", "openai", "google", "microsoft", "apple",
    "startup", "product", "launch", "research", "study", "data",
    "automation", "cloud", "security", "privacy", "blockchain",
    "web3", "metaverse", "ar", "vr", "quantum", "developer",
    "programming", "python", "javascript", "react", "kubernetes",
    "open source", "api", "saas", "b2b", "funding", "ipo",
    "sustainability", "climate", "health", "mental health",
    "productivity", "remote work", "future of work",
}


def _tokenize(text: str) -> list[str]:
    """Lowercase and extract words ≥ 3 chars, excluding stop words."""
    if not text:
        return []
    text = text.lower()
    words = re.findall(r'\b[a-z][a-z\-]{2,}\b', text)
    return [w for w in words if w not in STOP_WORDS]


def _extract_bigrams(tokens: list[str]) -> list[str]:
    """Create bigrams (two-word phrases) from token list."""
    bigrams = []
    for i in range(len(tokens) - 1):
        phrase = f"{tokens[i]} {tokens[i+1]}"
        bigrams.append(phrase)
    return bigrams


def extract_topics_from_text(text: str) -> list[tuple[str, int]]:
    """
    Extract the top N topics from a block of text.
    Returns list of (topic, frequency) tuples.
    """
    tokens = _tokenize(text)
    bigrams = _extract_bigrams(tokens)

    # Count unigrams and bigrams
    all_terms = tokens + bigrams
    counter = Counter(all_terms)

    # Apply boost multiplier to known important keywords
    boosted = {}
    for term, count in counter.items():
        if any(bk in term for bk in BOOST_KEYWORDS):
            boosted[term] = count * 2.5
        else:
            boosted[term] = float(count)

    # Sort by boosted score
    sorted_terms = sorted(boosted.items(), key=lambda x: x[1], reverse=True)

    # Filter: only keep terms appearing ≥ 2 times
    result = [(t, int(s)) for t, s in sorted_terms if s >= 2]
    return result[:20]


def analyze_articles_for_trends(limit: int = 100, days: int = 7) -> dict:
    """
    Analyse recent articles and update the topic_trends table.
    Returns a summary of what was analysed.
    """
    # Get recent articles
    articles = get_articles(limit=limit)
    if not articles:
        return {"topics_found": 0, "articles_analysed": 0}

    # Combine title + summary text for analysis
    combined_text = " ".join(
        f"{a.get('title', '')} {a.get('summary', '')}"
        for a in articles
    )

    # Extract topics and update DB
    topics = extract_topics_from_text(combined_text)
    for topic, freq in topics:
        # Determine category from article sources
        category = _guess_category(topic, articles)
        score = _calculate_score(topic, articles, freq)
        upsert_topic_trend(topic, category=category, score_delta=score)

    return {
        "topics_found": len(topics),
        "articles_analysed": len(articles),
        "top_topics": [t[0] for t in topics[:10]],
    }


def _guess_category(topic: str, articles: list) -> str:
    """Guess a category for a topic based on article categories."""
    topic_lower = topic.lower()
    # Simple rule-based mapping
    tech_words = {"ai", "machine learning", "cloud", "api", "code", "developer", "software", "python"}
    business_words = {"startup", "funding", "market", "revenue", "enterprise", "b2b"}
    science_words = {"research", "study", "university", "quantum", "data"}

    for w in tech_words:
        if w in topic_lower:
            return "Technology"
    for w in business_words:
        if w in topic_lower:
            return "Business"
    for w in science_words:
        if w in topic_lower:
            return "Science"

    # Fall back to most common category in articles mentioning this topic
    cat_counts = Counter()
    for a in articles:
        combined = f"{a.get('title','')} {a.get('summary','')}".lower()
        if topic_lower in combined:
            cat_counts[a.get("category", "General")] += 1

    if cat_counts:
        return cat_counts.most_common(1)[0][0]
    return "General"


def _calculate_score(topic: str, articles: list, base_freq: int) -> float:
    """
    Calculate a topic score based on:
    - Raw frequency
    - Number of unique articles it appears in
    - Recency boost (more recent = higher)
    """
    topic_lower = topic.lower()
    article_count = 0
    recency_boost = 0.0
    cutoff = datetime.utcnow() - timedelta(days=3)

    for a in articles:
        combined = f"{a.get('title','')} {a.get('summary','')}".lower()
        if topic_lower in combined:
            article_count += 1
            try:
                pub_str = a.get("published") or a.get("created_at", "")
                pub_date = datetime.fromisoformat(pub_str[:19])
                if pub_date >= cutoff:
                    recency_boost += 1.5
            except Exception:
                pass

    # Score formula: frequency × article spread + recency
    score = (base_freq * 0.5) + (article_count * 2.0) + recency_boost
    return round(score, 2)


def get_trending_hashtags(topic: str) -> list[str]:
    """Generate relevant hashtags for a topic (rule-based, no fake data)."""
    words = topic.lower().split()
    hashtags = []

    # Remove stop words and capitalise first letter
    for w in words:
        if w not in STOP_WORDS and len(w) >= 3:
            hashtags.append("#" + w.capitalize())

    # Add compound hashtag
    if len(words) >= 2:
        compound = "".join(w.capitalize() for w in words if w not in STOP_WORDS)
        if len(compound) <= 25:
            hashtags.append("#" + compound)

    return hashtags[:5]


def get_suggested_publishing_times() -> dict:
    """
    Returns general publishing time recommendations.
    Based on common content marketing guidelines — NOT fabricated analytics.
    """
    return {
        "disclaimer": "These are general recommendations based on industry guidelines, not your personal audience data.",
        "best_days": ["Tuesday", "Wednesday", "Thursday"],
        "best_times_utc": ["08:00", "12:00", "17:00"],
        "note": "Actual best times vary by audience and niche. Use your analytics platform for personalised insights.",
    }
