# PULSE — AI-Powered Writing Assistant

PULSE is a full-stack web application that helps bloggers manage information overload, discover blog ideas, and create better content — powered by IBM Granite via IBM watsonx.ai.

---

## Features

| Module | What it does |
|---|---|
| **Dashboard** | Overview stats, trending topics, recent drafts, Chart.js visualisations |
| **Discover** | RSS feeds, arXiv research papers, custom URL scraping, search & filter |
| **AI Intelligence** | IBM Granite-powered article analysis, theme identification, blog topic suggestions |
| **Idea Workspace** | Capture rough ideas, upload images, AI refinement, title & outline suggestions |
| **Blog Editor** | Write drafts, generate intros/conclusions/outlines, rewrite, expand, export TXT/MD |
| **Settings** | Configure IBM Granite credentials, manage RSS feeds, set interests |

---

## Technology Stack

- **Backend:** Python 3.11+, Flask 3
- **Database:** SQLite (file-based, zero config)
- **AI:** IBM Granite via `ibm-watsonx-ai` SDK
- **Frontend:** Vanilla HTML/CSS/JavaScript
- **Charts:** Chart.js (CDN)
- **Content:** `feedparser`, `requests`, `beautifulsoup4`

---

## Project Structure

```
pulse/
├── app.py                  # Flask app + all routes
├── config.py               # Configuration & environment variables
├── requirements.txt
├── .env.example            # Template for credentials
├── README.md
│
├── models/
│   └── database.py         # All SQLite operations
│
├── services/
│   ├── ai_service.py       # High-level AI operations (prompts + parsing)
│   ├── granite_service.py  # IBM watsonx.ai SDK wrapper + demo mode
│   ├── news_service.py     # RSS feeds, arXiv, URL scraping
│   └── content_analyzer.py # Topic extraction & trend scoring
│
├── templates/
│   ├── base.html           # Shared layout (sidebar, topbar)
│   ├── dashboard.html
│   ├── discover.html
│   ├── intelligence.html
│   ├── ideas.html
│   ├── editor.html
│   └── settings.html
│
├── static/
│   ├── css/style.css       # All styles (Notion/Linear-inspired)
│   └── js/script.js        # Global JS utilities
│
└── uploads/                # User-uploaded images
```

---

## Setup Instructions

### 1. Clone / download the project

```bash
cd pulse
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and add your IBM credentials:

```env
WATSONX_API_KEY=your_ibm_cloud_api_key
WATSONX_PROJECT_ID=your_watsonx_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
GRANITE_MODEL_ID=ibm/granite-13b-instruct-v2
SECRET_KEY=change-this-to-a-random-string
```

> **Demo Mode:** If you skip this step, PULSE runs in Demo Mode — all features work but AI responses are clearly labelled placeholder text.

### 5. Run the application

```bash
python app.py
```

Open your browser at: **http://localhost:5000**

---

## Getting IBM Granite Credentials

1. **Create an IBM Cloud account:** https://cloud.ibm.com/registration
2. **Create an API key:** https://cloud.ibm.com/iam/apikeys
3. **Create a watsonx.ai project:** https://dataplatform.cloud.ibm.com/projects
4. Copy the Project ID from your project's **Manage** tab
5. Add both values to your `.env` file or enter them in **Settings** inside PULSE

---

## Usage Guide

### Collecting Content
1. Go to **Discover** → click **Refresh Feeds** to fetch articles from all RSS sources
2. Click **arXiv** to search for research papers by topic
3. Click **+ Add URL** to submit any article URL or paste text directly

### AI Analysis
1. Go to **AI Intelligence**
2. Choose the scope (recent articles, all, or by category)
3. Select the analysis type (Full / Themes / Topics / Summary)
4. Click **Analyse with IBM Granite**
5. Save interesting suggestions with ⭐

### Writing a Blog Post
1. Go to **Idea Workspace** → capture your rough idea → click **Refine with AI**
2. Click **Start Draft** to open the idea in the Blog Editor
3. Use the toolbar to generate an **Introduction**, **Conclusion**, **Outline**, or **Expand** sections
4. Press **Ctrl+S** (or click Save) at any time
5. Export as **TXT** or **Markdown** when ready

---

## Demo Mode

When IBM Granite credentials are not configured:
- A yellow banner appears at the top of every page
- All AI buttons still work but return clearly labelled placeholder responses
- All other features (content collection, database, drafts, ideas) work normally

---

## Licence

MIT — free to use and modify.
