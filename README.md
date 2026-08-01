# Michael Nussbaum's Enterprise Thought Leadership Agent

A private Streamlit application that finds relevant articles, summarizes the available RSS information, captures Michael's point of view in three short inputs, and creates a manually reviewed LinkedIn draft.

The target publishing rhythm is **one to two strong posts per week**. The application is intentionally not an auto-publishing content factory.

## What It Does

1. Fetches recent articles from enterprise technology, web-platform, operations, leadership, and AI sources.
2. Scores articles against Michael's priority topics:
   - Global web operations
   - Enterprise web-platform governance
   - AI-assisted workflows and operational efficiency
   - Product operations
   - Change management
   - Future of work
3. Maintains a consumable article queue in `state.json`.
4. Generates a concise summary of the RSS-provided content and identifies a possible tension worth challenging.
5. Asks Michael for three inputs:
   - **What’s your reaction?**
   - **What have you seen in practice?**
   - **What should teams do differently?**
6. Generates one LinkedIn draft in Michael's personalized voice.
7. Leaves editing, copying, and publishing fully manual.

## Important Content Limitation

The current version summarizes the article title and RSS excerpt. It does **not** retrieve and analyze the complete article body. The summary prompt is designed not to imply otherwise.

Always open and read the full source before publishing a response, especially when the RSS excerpt is limited.

## Personalized Files

- `voice_profile.md` — positioning, audience, tone, role families, writing structure, and guardrails
- `experience_context.md` — private career context and safe-use rules
- `config/content_pillars.json` — audience and topic priorities
- `config/sources.json` — RSS feeds, weights, keywords, exclusions, and queue settings

## File Structure

```text
enterprise-thought-leadership-agent/
├── .github/workflows/
│   └── daily_article.yml
├── agent/
│   ├── fetch_articles.py
│   ├── generate_post.py
│   └── post_to_social.py       # legacy/unused; manual posting is the default
├── config/
│   ├── content_pillars.json
│   └── sources.json
├── app.py
├── experience_context.md
├── state.json
├── voice_profile.md
└── requirements.txt
```

## One-Time Setup

### 1. Create a private GitHub repository

Copy these files into a private repository. Do not commit API keys or access tokens.

### 2. Deploy with Streamlit Community Cloud

Connect the private GitHub repository and deploy `app.py`.

### 3. Add Streamlit secrets

```toml
APP_PASSWORD = "choose-a-strong-password"
ANTHROPIC_API_KEY = "your-key"
GITHUB_TOKEN = "token-with-access-to-this-private-repo"
GITHUB_OWNER = "your-github-username"
GITHUB_REPO = "your-repository-name"
GITHUB_BRANCH = "main"

# Optional model overrides
ANTHROPIC_SUMMARY_MODEL = "claude-sonnet-4-6"
ANTHROPIC_POST_MODEL = "claude-opus-4-8"
```

The application also reads environment variables, which Streamlit exposes from secrets.

### 4. Add GitHub Actions secrets

The scheduled article fetch only needs repository write permission. The current fetch script does not send email and does not require Anthropic.

Optional repository variable or secret:

```text
STREAMLIT_APP_URL=https://your-app.streamlit.app
```

## Queue and Schedule

The workflow runs on weekdays. RSS fetching is also triggered automatically when the Streamlit queue falls below its minimum.

Current defaults:

- Queue size: 10
- Freshness window: 5 days
- GitHub workflow: weekdays at 16:00 UTC

Edit `.github/workflows/daily_article.yml` or the `queue` object in `config/sources.json` to change them.

## Editorial Workflow

Before publishing:

1. Read the complete article.
2. Confirm that the generated draft accurately represents your point of view.
3. Remove claims or details that are not supported.
4. Confirm that named-company examples are positive, public, and appropriate.
5. Generalize sensitive setbacks, internal dysfunction, layoffs, budgets, or individual situations.
6. Publish manually to LinkedIn.

## Positioning Boundaries

The agent should position Michael around Product Operations, Global Web Operations, enterprise web-platform governance, and Senior Technical Production.

It should not present him as a loyalty, lifecycle-marketing, CRM-campaign, or MarTech leader. AI should appear as a practical method for improving operations rather than as a generic thought-leadership identity.

## Legacy Social Posting File

`agent/post_to_social.py` remains in the repository as inherited code, but the Streamlit application does not call it. Manual LinkedIn publishing is the chosen workflow and avoids accidental posting.
