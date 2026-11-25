import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "pulse-dev-secret-key-change-in-production")
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"

    # Database
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, "pulse.db")

    # IBM watsonx.ai
    WATSONX_API_KEY = os.getenv("WATSONX_API_KEY", "")
    WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "")
    WATSONX_URL = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

    # IBM Granite model
    GRANITE_MODEL_ID = os.getenv("GRANITE_MODEL_ID", "ibm/granite-13b-instruct-v2")

    # Demo mode: automatically enabled when watsonx credentials are missing
    @staticmethod
    def is_demo_mode():
        api_key = os.getenv("WATSONX_API_KEY", "")
        project_id = os.getenv("WATSONX_PROJECT_ID", "")
        return not (api_key and project_id)

    # RSS Feed sources
    RSS_FEEDS = [
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "Technology"},
        {"name": "Wired", "url": "https://www.wired.com/feed/rss", "category": "Technology"},
        {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/", "category": "Technology"},
        {"name": "HBR", "url": "https://feeds.hbr.org/harvardbusiness", "category": "Business"},
        {"name": "Medium - Programming", "url": "https://medium.com/feed/tag/programming", "category": "Programming"},
        {"name": "Dev.to", "url": "https://dev.to/feed", "category": "Programming"},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "Technology"},
    ]

    # Upload settings
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # Content fetch limits
    MAX_ARTICLES_PER_FEED = 20
    ARXIV_MAX_RESULTS = 10

    # Topic categories for interest tracking
    DEFAULT_INTERESTS = [
        "Technology", "AI & Machine Learning", "Business", "Programming",
        "Science", "Design", "Marketing", "Productivity"
    ]
