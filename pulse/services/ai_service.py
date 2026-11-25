"""
ai_service.py — High-level AI operations built on top of granite_service.
Each function builds a prompt and parses the response from IBM Granite.
"""

import json
import re
from services.granite_service import call_granite


# ── Prompt builder helpers ────────────────────────────────────────────────────

def _prompt(system: str, user: str) -> str:
    return f"<|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>\n"


TONE_DESCRIPTIONS = {
    "professional":    "formal, authoritative and polished",
    "conversational":  "friendly, approachable and easy to read",
    "informative":     "clear, educational and fact-focused",
    "persuasive":      "compelling, motivating and action-oriented",
}


# ── Content Analysis ──────────────────────────────────────────────────────────

def analyse_articles(articles: list, analysis_type: str = "full") -> dict:
    """
    Analyse a list of articles with IBM Granite.
    analysis_type: 'full' | 'themes' | 'topics' | 'summary'
    """
    if not articles:
        return {"error": "No articles to analyse. Collect some content first.", "result": ""}

    # Build article digest (title + summary for each)
    digest_parts = []
    for i, a in enumerate(articles[:20], 1):
        title   = a.get("title", "")
        summary = a.get("summary", "")[:200]
        source  = a.get("source", "")
        digest_parts.append(f"{i}. [{source}] {title}\n   {summary}")

    digest = "\n\n".join(digest_parts)

    if analysis_type == "summary":
        prompt = _prompt(
            "You are a content analyst. Summarise the following articles concisely.",
            f"Articles:\n{digest}\n\nProvide a 2-3 paragraph summary of the main themes."
        )
    elif analysis_type == "themes":
        prompt = _prompt(
            "You are a content strategist. Identify common themes across these articles.",
            f"Articles:\n{digest}\n\nList the top 5-7 emerging themes with a one-sentence explanation each."
        )
    elif analysis_type == "topics":
        prompt = _prompt(
            "You are a blog strategist. Suggest blog topics based on these articles.",
            f"Articles:\n{digest}\n\n"
            "Suggest 5 interesting blog topics. For each, provide:\n"
            "- Topic title\n- One-sentence explanation of why it's worth writing about\n"
            "- 3 keywords\n- 2 alternative title options"
        )
    else:  # full
        prompt = _prompt(
            "You are a content intelligence analyst. Provide a comprehensive analysis.",
            f"Articles:\n{digest}\n\n"
            "Provide:\n"
            "1. A brief summary (2 paragraphs)\n"
            "2. Top 5 themes (one sentence each)\n"
            "3. 3 blog topic suggestions with reasoning\n"
            "4. 5 recommended keywords"
        )

    result = call_granite(prompt, max_tokens=1000)

    if not result["success"]:
        return {"error": result.get("error", "AI call failed"), "result": ""}

    text = result["text"]

    # Try to extract structured topics for the topics view
    topics = []
    if analysis_type in ("topics", "full"):
        topics = _extract_topics_from_text(text)

    return {
        "result": text,
        "topics": topics,
        "demo": result.get("demo", False),
    }


def _extract_topics_from_text(text: str) -> list:
    """
    Parse structured topics from Granite's plain-text response.
    Returns list of dicts with title, explanation, keywords, titles.
    """
    topics = []
    lines = text.split("\n")
    current = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Detect numbered topic headers like "1. Topic Name" or "**Topic Name**"
        if re.match(r'^[\d]+[\.\)]\s+.{10,}', line) or re.match(r'^\*\*.{5,}\*\*', line):
            if current.get("title"):
                topics.append(current)
            title = re.sub(r'^[\d]+[\.\)]\s*', '', line)
            title = re.sub(r'\*\*', '', title).strip()
            current = {"title": title, "explanation": "", "keywords": [], "titles": []}
        elif current.get("title"):
            if any(w in line.lower() for w in ["keyword", "keywords:", "tags:"]):
                # Extract keywords from the line
                kw_part = re.sub(r'keywords?:?\s*', '', line, flags=re.I)
                keywords = [k.strip().strip('*#-') for k in re.split(r'[,;|]', kw_part) if k.strip()]
                current["keywords"] = keywords[:5]
            elif any(w in line.lower() for w in ["alternative", "alt title", "other title"]):
                pass  # Skip header lines
            elif line.startswith("-") or line.startswith("•"):
                clean = line.lstrip("-•").strip()
                if clean and len(clean) > 10:
                    current["titles"].append(clean)
            elif not current.get("explanation") and len(line) > 20:
                current["explanation"] = line

    if current.get("title"):
        topics.append(current)

    return topics[:6]


# ── Idea Refinement ───────────────────────────────────────────────────────────

def refine_idea(raw_text: str, tone: str = "professional") -> dict:
    """
    Take a rough idea and return a refined concept with titles and keywords.
    """
    tone_desc = TONE_DESCRIPTIONS.get(tone, "professional")
    prompt = _prompt(
        f"You are a creative writing coach who helps bloggers develop their ideas. "
        f"Your writing style is {tone_desc}.",
        f"Here is my rough blog idea:\n\n{raw_text}\n\n"
        "Please:\n"
        "1. Refine this into a clear, compelling blog concept (2-3 sentences)\n"
        "2. Suggest 3 blog post titles (numbered)\n"
        "3. Recommend 5 SEO keywords (comma-separated)\n"
        "4. Suggest a recommended writing tone and structure"
    )

    result = call_granite(prompt, max_tokens=600)

    if not result["success"]:
        return {"error": result.get("error", "Failed to refine idea")}

    text = result["text"]
    titles = _extract_numbered_list(text)[:3]
    keywords = _extract_keywords(text)

    return {
        "refined":  text,
        "titles":   titles,
        "keywords": keywords,
        "demo":     result.get("demo", False),
    }


# ── Outline Generation ────────────────────────────────────────────────────────

def generate_outline(title: str, tone: str = "professional") -> dict:
    """Generate a blog post outline for the given title."""
    tone_desc = TONE_DESCRIPTIONS.get(tone, "professional")
    prompt = _prompt(
        f"You are a professional blog writer. Create clear, logical blog outlines. "
        f"Writing tone: {tone_desc}.",
        f"Create a detailed blog post outline for:\n\n\"{title}\"\n\n"
        "Format as a numbered list of sections with one sub-point each. "
        "Include Introduction and Conclusion. Keep it to 6-8 sections."
    )

    result = call_granite(prompt, max_tokens=400)

    if not result["success"]:
        return {"error": result.get("error", "Failed to generate outline"), "outline": ""}

    return {"outline": result["text"], "demo": result.get("demo", False)}


# ── Blog Writing Assistance ───────────────────────────────────────────────────

def generate_introduction(title: str, content: str = "", tone: str = "professional") -> dict:
    tone_desc = TONE_DESCRIPTIONS.get(tone, "professional")
    context = f"Draft context:\n{content[:300]}\n\n" if content else ""
    prompt = _prompt(
        f"You are a skilled blog writer. Tone: {tone_desc}.",
        f"{context}Write an engaging introduction (2-3 paragraphs) for a blog post titled:\n\"{title}\""
    )
    result = call_granite(prompt, max_tokens=400)
    return {"result": result["text"], "demo": result.get("demo", False)} if result["success"] \
        else {"error": result.get("error", "Failed")}


def generate_conclusion(title: str, content: str = "", tone: str = "professional") -> dict:
    tone_desc = TONE_DESCRIPTIONS.get(tone, "professional")
    summary = content[:800] if content else title
    prompt = _prompt(
        f"You are a skilled blog writer. Tone: {tone_desc}.",
        f"Based on this blog post about \"{title}\":\n\n{summary}\n\n"
        "Write a compelling conclusion (2-3 paragraphs) that summarises the key points and provides a call to action."
    )
    result = call_granite(prompt, max_tokens=400)
    return {"result": result["text"], "demo": result.get("demo", False)} if result["success"] \
        else {"error": result.get("error", "Failed")}


def expand_text(selected: str, title: str = "", tone: str = "professional") -> dict:
    tone_desc = TONE_DESCRIPTIONS.get(tone, "professional")
    prompt = _prompt(
        f"You are a skilled blog writer. Tone: {tone_desc}.",
        f"Expand and develop the following text from a blog post about \"{title}\":\n\n{selected}\n\n"
        "Add more detail, examples, and context. Write 2-4 paragraphs."
    )
    result = call_granite(prompt, max_tokens=500)
    return {"result": result["text"], "demo": result.get("demo", False)} if result["success"] \
        else {"error": result.get("error", "Failed")}


def expand_section(section_title: str, blog_title: str = "", tone: str = "professional") -> dict:
    tone_desc = TONE_DESCRIPTIONS.get(tone, "professional")
    prompt = _prompt(
        f"You are a skilled blog writer. Tone: {tone_desc}.",
        f"Write a full section for a blog post. The section is:\n\n\"{section_title}\"\n\n"
        f"This is part of a blog titled: \"{blog_title}\"\n\n"
        "Write 2-3 well-structured paragraphs for this section."
    )
    result = call_granite(prompt, max_tokens=500)
    return {"result": result["text"], "demo": result.get("demo", False)} if result["success"] \
        else {"error": result.get("error", "Failed")}


def rewrite_text(selected: str, tone: str = "professional") -> dict:
    tone_desc = TONE_DESCRIPTIONS.get(tone, "professional")
    prompt = _prompt(
        f"You are an expert editor. Rewrite in a {tone_desc} style.",
        f"Rewrite the following text to improve clarity, flow and engagement:\n\n{selected}"
    )
    result = call_granite(prompt, max_tokens=len(selected.split()) * 2 + 200)
    return {"result": result["text"], "demo": result.get("demo", False)} if result["success"] \
        else {"error": result.get("error", "Failed")}


def suggest_keywords(title: str, content: str = "") -> dict:
    context = content[:400] if content else title
    prompt = _prompt(
        "You are an SEO specialist.",
        f"Suggest 10 relevant SEO keywords for a blog post titled \"{title}\".\n"
        f"Context: {context}\n\n"
        "Return a comma-separated list of keywords only."
    )
    result = call_granite(prompt, max_tokens=150)
    if not result["success"]:
        return {"keywords": [], "error": result.get("error")}
    keywords = _extract_keywords(result["text"])
    return {"keywords": keywords, "demo": result.get("demo", False)}


def run_custom_prompt(prompt_text: str, title: str, content: str, tone: str) -> dict:
    tone_desc = TONE_DESCRIPTIONS.get(tone, "professional")
    context = ""
    if title:
        context += f"Blog title: {title}\n"
    if content:
        context += f"Current content (excerpt): {content[:400]}\n"
    prompt = _prompt(
        f"You are a helpful writing assistant. Tone: {tone_desc}.",
        f"{context}\nUser instruction: {prompt_text}"
    )
    result = call_granite(prompt, max_tokens=600)
    return {"result": result["text"], "demo": result.get("demo", False)} if result["success"] \
        else {"error": result.get("error", "Failed")}


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _extract_numbered_list(text: str) -> list:
    """Extract items from a numbered list in text."""
    items = []
    for match in re.finditer(r'^\s*[\d]+[\.\)]\s+(.+)', text, re.MULTILINE):
        item = match.group(1).strip().strip('*').strip()
        if item and len(item) > 5:
            items.append(item)
    return items


def _extract_keywords(text: str) -> list:
    """Extract keywords from a text block (looks for comma-separated lines)."""
    # Find the last comma-separated section
    for line in reversed(text.split('\n')):
        line = line.strip()
        if ',' in line and len(line) > 10:
            keywords = [k.strip().strip('*#-\'"').lower() for k in line.split(',')]
            keywords = [k for k in keywords if k and len(k) >= 3 and len(k) <= 40]
            if keywords:
                return keywords[:10]

    # Fallback: extract any word-looking phrases
    kw_match = re.search(r'keywords?:?\s*(.+)', text, re.I)
    if kw_match:
        raw = kw_match.group(1)
        keywords = [k.strip().strip('*#-').lower() for k in re.split(r'[,;|]', raw) if k.strip()]
        return keywords[:10]
    return []
