"""
granite_service.py — IBM Granite via watsonx.ai SDK.
Falls back to demo mode when credentials are not configured.
"""

import os
import json
from config import Config

# Try to import the IBM watsonx.ai SDK
try:
    from ibm_watsonx_ai import APIClient, Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    print("[WARN] ibm-watsonx-ai not installed - running in demo mode.")


def _get_client():
    """Create and return a watsonx.ai APIClient using current env/settings."""
    api_key    = os.getenv("WATSONX_API_KEY", Config.WATSONX_API_KEY)
    url        = os.getenv("WATSONX_URL", Config.WATSONX_URL)
    project_id = os.getenv("WATSONX_PROJECT_ID", Config.WATSONX_PROJECT_ID)

    if not api_key or not project_id:
        return None, None

    try:
        credentials = Credentials(url=url, api_key=api_key)
        client = APIClient(credentials=credentials, project_id=project_id)
        return client, project_id
    except Exception as e:
        print(f"[WARN] watsonx client error: {e}")
        return None, None


def call_granite(prompt: str, max_tokens: int = 800, temperature: float = 0.7) -> dict:
    """
    Call IBM Granite model with a prompt.
    Returns {"success": bool, "text": str, "demo": bool}
    """
    # Demo mode guard
    if Config.is_demo_mode() or not SDK_AVAILABLE:
        return {"success": True, "text": _demo_response(prompt), "demo": True}

    client, project_id = _get_client()
    if not client:
        return {"success": False, "error": "Could not connect to watsonx.ai. Check your credentials in Settings.",
                "text": "", "demo": False}

    model_id = os.getenv("GRANITE_MODEL_ID", Config.GRANITE_MODEL_ID)

    params = {
        GenParams.MAX_NEW_TOKENS: max_tokens,
        GenParams.TEMPERATURE:    temperature,
        GenParams.STOP_SEQUENCES: ["Human:", "User:"],
        GenParams.REPETITION_PENALTY: 1.1,
    }

    try:
        model = ModelInference(
            model_id=model_id,
            api_client=client,
            project_id=project_id,
            params=params,
        )
        response = model.generate_text(prompt=prompt)
        text = response.strip() if isinstance(response, str) else str(response)
        return {"success": True, "text": text, "demo": False}
    except Exception as e:
        print(f"[WARN] Granite generation error: {e}")
        return {"success": False, "error": str(e), "text": "", "demo": False}


def test_connection() -> dict:
    """
    Test watsonx.ai connection with a minimal prompt.
    Returns {"success": bool, "message": str}
    """
    if not SDK_AVAILABLE:
        return {"success": False, "error": "ibm-watsonx-ai SDK is not installed. Run: pip install ibm-watsonx-ai"}

    if Config.is_demo_mode():
        return {"success": False, "error": "No credentials configured. Add WATSONX_API_KEY and WATSONX_PROJECT_ID."}

    result = call_granite("Say hello in one sentence.", max_tokens=50)
    if result["success"]:
        return {"success": True, "message": f"Connected! Granite responded: {result['text'][:100]}"}
    return {"success": False, "error": result.get("error", "Unknown error")}


# ── Demo mode responses ───────────────────────────────────────────────────────

def _demo_response(prompt: str) -> str:
    """
    Return a clearly labelled demo response when credentials are absent.
    Does not fabricate real content — only placeholder text.
    """
    p = prompt.lower()

    if "summarise" in p or "summary" in p or "summarize" in p:
        return (
            "[DEMO MODE — IBM Granite not connected]\n\n"
            "This is a placeholder summary. In production, IBM Granite would analyse the "
            "provided articles and return a concise summary of the key points, common themes, "
            "and emerging ideas found across the content.\n\n"
            "To enable real AI responses, add your IBM Cloud API key and watsonx.ai "
            "Project ID in Settings."
        )

    if "topic" in p or "blog idea" in p or "suggest" in p:
        return (
            "[DEMO MODE — IBM Granite not connected]\n\n"
            "Example topic suggestions that Granite would generate:\n\n"
            "1. The Rise of Agentic AI — Why autonomous agents are changing software development\n"
            "2. Developer Experience in 2025 — What engineers really want from tooling\n"
            "3. The Hidden Cost of Technical Debt — A practical guide to paying it back\n\n"
            "These are placeholder examples only. Connect IBM Granite for real, context-aware suggestions."
        )

    if "outline" in p:
        return (
            "[DEMO MODE]\n\n"
            "Introduction\n"
            "1. Background and Context\n"
            "2. Key Challenges\n"
            "3. Current Solutions\n"
            "4. Best Practices\n"
            "5. Case Studies\n"
            "6. Future Outlook\n"
            "Conclusion\n\n"
            "Connect IBM Granite for a real outline tailored to your topic."
        )

    if "introduction" in p or "intro" in p:
        return (
            "[DEMO MODE]\n\n"
            "In a world where technology evolves faster than ever, understanding the topic "
            "of [your subject] has become essential for every professional. This post explores "
            "the key aspects, challenges, and opportunities that define this space today.\n\n"
            "Connect IBM Granite for a real, context-aware introduction."
        )

    if "conclusion" in p:
        return (
            "[DEMO MODE]\n\n"
            "The insights explored throughout this post highlight a clear direction: thoughtful "
            "application of [your subject] creates measurable value. As the landscape continues "
            "to evolve, staying informed and adaptable will be the defining trait of success.\n\n"
            "Connect IBM Granite for a real conclusion tailored to your content."
        )

    if "rewrite" in p or "improve" in p:
        return "[DEMO MODE] Your selected text would be rewritten with improved clarity and flow by IBM Granite."

    if "expand" in p:
        return "[DEMO MODE] IBM Granite would expand this section with additional context, examples, and details."

    if "keyword" in p:
        return "[DEMO MODE] Keywords: content strategy, AI tools, writing productivity, blog growth, SEO optimisation"

    if "refine" in p or "idea" in p:
        return (
            "[DEMO MODE — IBM Granite not connected]\n\n"
            "Your rough idea would be refined into a clear, compelling blog concept with:\n"
            "• A focused angle and target audience\n"
            "• Key questions to answer\n"
            "• Recommended tone and structure\n"
            "• Three to five blog title options\n\n"
            "Connect IBM Granite in Settings to enable this feature."
        )

    # Generic fallback
    return (
        "[DEMO MODE — IBM Granite not connected]\n\n"
        "This is a placeholder AI response. Configure your IBM Cloud API key "
        "and watsonx.ai Project ID in Settings to enable real IBM Granite AI features."
    )
