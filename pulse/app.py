"""
app.py — PULSE Flask application entry point.
Registers all routes: page views and JSON API endpoints.
"""

import os
import json
from flask import (
    Flask, render_template, request, jsonify, send_from_directory, abort
)
from werkzeug.utils import secure_filename
from config import Config
from models.database import (
    init_db,
    get_articles, get_article_count, get_articles_by_ids,
    insert_article,
    get_ideas, get_idea, save_idea, update_idea, delete_idea,
    get_drafts, get_draft, save_draft, update_draft, delete_draft,
    get_saved_suggestions, save_suggestion, delete_suggestion,
    get_trending_topics,
    get_setting, set_setting, get_all_settings,
    add_custom_feed, get_custom_feeds, delete_custom_feed,
    get_dashboard_stats,
)

# ── App setup ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config.from_object(Config)
app.config["UPLOAD_FOLDER"] = Config.UPLOAD_FOLDER

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
init_db()

# ── Template helpers ──────────────────────────────────────────────────────────

def base_ctx() -> dict:
    """Context variables injected into every page render."""
    return {"demo_mode": Config.is_demo_mode()}


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def dashboard():
    stats = get_dashboard_stats()
    return render_template("dashboard.html", stats=stats, active_page="dashboard", **base_ctx())


@app.route("/discover")
def discover():
    return render_template("discover.html", active_page="discover", **base_ctx())


@app.route("/intelligence")
def intelligence():
    return render_template("intelligence.html", active_page="intelligence", **base_ctx())


@app.route("/ideas")
def ideas():
    return render_template("ideas.html", active_page="ideas", **base_ctx())


@app.route("/editor")
def editor():
    return render_template("editor.html", active_page="editor", **base_ctx())


@app.route("/settings")
def settings():
    interests_raw = get_setting("interests", "[]")
    try:
        user_interests = json.loads(interests_raw)
    except Exception:
        user_interests = []

    return render_template(
        "settings.html",
        active_page="settings",
        builtin_feeds=Config.RSS_FEEDS,
        default_interests=Config.DEFAULT_INTERESTS,
        user_interests=user_interests,
        **base_ctx()
    )


# Serve uploaded images
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ═══════════════════════════════════════════════════════════════════════════════
# API — ARTICLES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/articles")
def api_articles():
    page     = max(1, int(request.args.get("page", 1)))
    limit    = min(50, int(request.args.get("limit", 24)))
    search   = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    offset   = (page - 1) * limit

    articles = get_articles(search=search, category=category, limit=limit, offset=offset)
    total    = get_article_count()

    # Quick count with filters applied
    if search or category:
        # Count matching records
        all_matching = get_articles(search=search, category=category, limit=10000, offset=0)
        total = len(all_matching)

    import math
    pages = max(1, math.ceil(total / limit))

    return jsonify({"articles": articles, "total": total, "page": page, "pages": pages})


@app.route("/api/fetch-feeds", methods=["POST"])
def api_fetch_feeds():
    from services.news_service import fetch_all_feeds
    from services.content_analyzer import analyze_articles_for_trends
    result = fetch_all_feeds()
    # Update trends after fetching
    analyze_articles_for_trends(limit=200)
    return jsonify(result)


@app.route("/api/fetch-arxiv", methods=["POST"])
def api_fetch_arxiv():
    data = request.get_json() or {}
    query    = data.get("query", "").strip()
    category = data.get("category", "cs.AI")
    if not query:
        return jsonify({"error": "Query is required"}), 400
    from services.news_service import fetch_arxiv
    from services.content_analyzer import analyze_articles_for_trends
    result = fetch_arxiv(query, category)
    analyze_articles_for_trends(limit=200)
    return jsonify(result)


@app.route("/api/add-content", methods=["POST"])
def api_add_content():
    data     = request.get_json() or {}
    url      = data.get("url", "").strip()
    text     = data.get("text", "").strip()
    title    = data.get("title", "").strip()
    category = data.get("category", "General")

    if url:
        from services.news_service import fetch_url_content
        scraped = fetch_url_content(url)
        if "error" in scraped:
            return jsonify({"error": scraped["error"]}), 400
        article = {
            "title":    title or scraped.get("title", url),
            "summary":  text or scraped.get("summary", ""),
            "url":      url,
            "source":   "Custom",
            "category": category,
            "image_url": scraped.get("image_url", ""),
        }
    elif text:
        article = {
            "title":    title or text[:60] + "…",
            "summary":  text[:500],
            "url":      f"custom://{abs(hash(text))}",
            "source":   "Custom",
            "category": category,
        }
    else:
        return jsonify({"error": "Provide URL or text"}), 400

    inserted = insert_article(article)
    if inserted:
        return jsonify({"message": "Content added successfully", "id": inserted})
    return jsonify({"message": "Content already exists (duplicate)."})


# ═══════════════════════════════════════════════════════════════════════════════
# API — AI ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/analyse", methods=["POST"])
def api_analyse():
    data     = request.get_json() or {}
    scope    = data.get("scope", "recent")
    category = data.get("category", "")
    atype    = data.get("type", "full")

    if scope == "recent":
        articles = get_articles(limit=20)
    elif scope == "category" and category:
        articles = get_articles(category=category, limit=30)
    else:
        articles = get_articles(limit=50)

    from services.ai_service import analyse_articles
    result = analyse_articles(articles, analysis_type=atype)
    return jsonify(result)


@app.route("/api/refine-idea", methods=["POST"])
def api_refine_idea():
    data     = request.get_json() or {}
    raw_text = data.get("raw_text", "").strip()
    tone     = data.get("tone", "professional")

    if not raw_text:
        return jsonify({"error": "No idea text provided"}), 400

    from services.ai_service import refine_idea
    result = refine_idea(raw_text, tone)
    return jsonify(result)


@app.route("/api/generate-outline", methods=["POST"])
def api_generate_outline():
    data  = request.get_json() or {}
    title = data.get("title", "").strip()
    tone  = data.get("tone", "professional")

    if not title:
        return jsonify({"error": "Title is required"}), 400

    from services.ai_service import generate_outline
    result = generate_outline(title, tone)
    return jsonify(result)


@app.route("/api/editor-ai", methods=["POST"])
def api_editor_ai():
    data     = request.get_json() or {}
    atype    = data.get("type", "intro")
    title    = data.get("title", "")
    content  = data.get("content", "")
    selected = data.get("selected", "")
    tone     = data.get("tone", "professional")
    prompt   = data.get("prompt", "")

    from services.ai_service import (
        generate_introduction, generate_conclusion,
        expand_text, expand_section, rewrite_text, suggest_keywords,
        run_custom_prompt
    )

    if atype == "intro":
        return jsonify(generate_introduction(title, content, tone))
    elif atype == "conclusion":
        return jsonify(generate_conclusion(title, content, tone))
    elif atype == "expand":
        return jsonify(expand_text(selected or content[:500], title, tone))
    elif atype == "expand_section":
        return jsonify(expand_section(title, blog_title=data.get("blog_title", ""), tone=tone))
    elif atype == "rewrite":
        return jsonify(rewrite_text(selected or content[:500], tone))
    elif atype == "keywords":
        return jsonify(suggest_keywords(title, content))
    elif atype == "custom":
        return jsonify(run_custom_prompt(prompt, title, content, tone))
    else:
        return jsonify({"error": f"Unknown action type: {atype}"}), 400


# ═══════════════════════════════════════════════════════════════════════════════
# API — IDEAS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/ideas", methods=["GET"])
def api_get_ideas():
    return jsonify({"ideas": get_ideas()})


@app.route("/api/ideas/<int:idea_id>", methods=["GET"])
def api_get_idea(idea_id):
    idea = get_idea(idea_id)
    if not idea:
        return jsonify({"error": "Not found"}), 404
    return jsonify(idea)


@app.route("/api/ideas", methods=["POST"])
def api_save_idea():
    data = request.get_json() or {}
    if not data.get("raw_text"):
        return jsonify({"error": "raw_text is required"}), 400
    idea_id = save_idea(data)
    return jsonify({"id": idea_id, "message": "Idea saved"})


@app.route("/api/ideas/<int:idea_id>", methods=["PUT"])
def api_update_idea(idea_id):
    data = request.get_json() or {}
    # Remove id key if present
    data.pop("id", None)
    update_idea(idea_id, data)
    return jsonify({"message": "Updated"})


@app.route("/api/ideas/<int:idea_id>", methods=["DELETE"])
def api_delete_idea(idea_id):
    delete_idea(idea_id)
    return jsonify({"message": "Deleted"})


# ═══════════════════════════════════════════════════════════════════════════════
# API — DRAFTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/drafts", methods=["GET"])
def api_get_drafts():
    drafts = get_drafts()
    return jsonify({"drafts": drafts})


@app.route("/api/drafts/<int:draft_id>", methods=["GET"])
def api_get_draft(draft_id):
    draft = get_draft(draft_id)
    if not draft:
        return jsonify({"error": "Not found"}), 404
    return jsonify(draft)


@app.route("/api/drafts", methods=["POST"])
def api_save_draft():
    data = request.get_json() or {}
    if not data.get("title"):
        data["title"] = "Untitled"
    draft_id = save_draft(data)
    total = len(get_drafts())
    return jsonify({"id": draft_id, "message": "Draft saved", "total_drafts": total})


@app.route("/api/drafts/<int:draft_id>", methods=["PUT"])
def api_update_draft(draft_id):
    data = request.get_json() or {}
    data.pop("id", None)
    update_draft(draft_id, data)
    return jsonify({"message": "Updated"})


@app.route("/api/drafts/<int:draft_id>", methods=["DELETE"])
def api_delete_draft(draft_id):
    delete_draft(draft_id)
    return jsonify({"message": "Deleted"})


# ═══════════════════════════════════════════════════════════════════════════════
# API — SUGGESTIONS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/suggestions", methods=["GET"])
def api_get_suggestions():
    return jsonify({"suggestions": get_saved_suggestions()})


@app.route("/api/suggestions", methods=["POST"])
def api_save_suggestion():
    data = request.get_json() or {}
    if not data.get("topic"):
        return jsonify({"error": "topic is required"}), 400
    suggestion_id = save_suggestion(data)
    return jsonify({"id": suggestion_id, "message": "Saved"})


@app.route("/api/suggestions/<int:suggestion_id>", methods=["DELETE"])
def api_delete_suggestion(suggestion_id):
    delete_suggestion(suggestion_id)
    return jsonify({"message": "Deleted"})


# ═══════════════════════════════════════════════════════════════════════════════
# API — SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/settings/ai", methods=["POST"])
def api_save_ai_settings():
    """Save watsonx credentials to .env file and re-test connection."""
    data = request.get_json() or {}
    api_key    = data.get("api_key", "").strip()
    project_id = data.get("project_id", "").strip()
    model_id   = data.get("model_id", Config.GRANITE_MODEL_ID)

    if not api_key or not project_id:
        return jsonify({"success": False, "error": "API key and Project ID are required"}), 400

    # Update environment variables in memory for the current process
    os.environ["WATSONX_API_KEY"]    = api_key
    os.environ["WATSONX_PROJECT_ID"] = project_id
    os.environ["GRANITE_MODEL_ID"]   = model_id

    # Persist to .env file
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    _write_env_file(env_path, {
        "WATSONX_API_KEY":    api_key,
        "WATSONX_PROJECT_ID": project_id,
        "WATSONX_URL":        Config.WATSONX_URL,
        "GRANITE_MODEL_ID":   model_id,
    })

    # Test the connection
    from services.granite_service import test_connection
    test_result = test_connection()
    if test_result["success"]:
        return jsonify({"success": True, "message": test_result["message"]})
    return jsonify({"success": False, "error": test_result["error"]})


@app.route("/api/settings/test-ai")
def api_test_ai():
    from services.granite_service import test_connection
    result = test_connection()
    return jsonify(result)


@app.route("/api/settings/interests", methods=["POST"])
def api_save_interests():
    data = request.get_json() or {}
    interests = data.get("interests", [])
    set_setting("interests", json.dumps(interests))
    return jsonify({"message": "Interests saved"})


def _write_env_file(path: str, updates: dict):
    """Write/update key=value pairs in a .env file."""
    existing = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()
    existing.update(updates)
    with open(path, "w", encoding="utf-8") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")


# ═══════════════════════════════════════════════════════════════════════════════
# API — FEEDS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/feeds", methods=["GET"])
def api_get_feeds():
    return jsonify({"feeds": get_custom_feeds()})


@app.route("/api/feeds", methods=["POST"])
def api_add_feed():
    data = request.get_json() or {}
    name     = data.get("name", "").strip()
    url      = data.get("url", "").strip()
    category = data.get("category", "General")
    if not name or not url:
        return jsonify({"error": "Name and URL required"}), 400
    feed_id = add_custom_feed(name, url, category)
    return jsonify({"id": feed_id, "message": "Feed added"})


@app.route("/api/feeds/<int:feed_id>", methods=["DELETE"])
def api_delete_feed(feed_id):
    delete_custom_feed(feed_id)
    return jsonify({"message": "Deleted"})


# ═══════════════════════════════════════════════════════════════════════════════
# API — IMAGE UPLOAD
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/upload-image", methods=["POST"])
def api_upload_image():
    if "image" not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in Config.ALLOWED_EXTENSIONS:
        return jsonify({"error": f"File type .{ext} not allowed"}), 400

    filename = secure_filename(file.filename)
    # Prefix with timestamp to avoid collisions
    import time
    filename = f"{int(time.time())}_{filename}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    return jsonify({"filename": filename, "path": f"uploads/{filename}"})


# ═══════════════════════════════════════════════════════════════════════════════
# API — ADMIN / DATA MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/admin/clear-articles", methods=["POST"])
def api_clear_articles():
    from models.database import get_db
    conn = get_db()
    conn.execute("DELETE FROM articles")
    conn.commit()
    conn.close()
    return jsonify({"message": "All articles cleared"})


@app.route("/api/admin/clear-trends", methods=["POST"])
def api_clear_trends():
    from models.database import get_db
    conn = get_db()
    conn.execute("DELETE FROM topic_trends")
    conn.commit()
    conn.close()
    return jsonify({"message": "Trends reset"})


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return render_template("dashboard.html",
                           stats=get_dashboard_stats(),
                           active_page="dashboard",
                           **base_ctx()), 404


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error", "detail": str(e)}), 500
    return jsonify({"error": str(e)}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting PULSE...")
    print(f"   Demo mode: {Config.is_demo_mode()}")
    print(f"   Database:  {Config.DATABASE_PATH}")
    app.run(debug=Config.DEBUG, port=5000, host="0.0.0.0")
