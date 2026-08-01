"""Generate an article summary and a single LinkedIn draft in Michael's voice."""

import json
import os
from pathlib import Path

import anthropic

ROOT = Path(__file__).parent.parent
VOICE_PROFILE_PATH = ROOT / "voice_profile.md"
EXPERIENCE_CONTEXT_PATH = ROOT / "experience_context.md"

SUMMARY_MODEL = os.getenv("ANTHROPIC_SUMMARY_MODEL", "claude-sonnet-4-6")
POST_MODEL = os.getenv("ANTHROPIC_POST_MODEL", "claude-opus-4-8")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_voice_profile() -> str:
    return _read(VOICE_PROFILE_PATH)


def load_experience_context() -> str:
    return _read(EXPERIENCE_CONTEXT_PATH)


def generate_summary(article: dict) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=420,
        messages=[{
            "role": "user",
            "content": f"""Summarize the supplied RSS article information for an experienced enterprise product and global web operations practitioner.

Return four compact sections in plain text:
1. What happened or what the author argues (2-3 sentences)
2. Why it matters for enterprise web, product operations, governance, change management, AI-assisted workflows, or the future of work (1-2 sentences)
3. One assumption or tension worth challenging (1 sentence)
4. Best-fit content pillar (choose one)

Do not claim you read the full article. The available content may be only an RSS excerpt. Be precise about that limitation when the excerpt is thin.

Title: {article.get('title', '')}
Source: {article.get('source', '')}
RSS excerpt: {article.get('summary', '')}"""
        }],
    )
    return message.content[0].text.strip()


def generate_post(article: dict, reaction: str, experience: str, recommendation: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    voice_profile = load_voice_profile()
    experience_context = load_experience_context()

    system_prompt = f"""You are Michael Nussbaum's LinkedIn ghostwriter.

Your purpose is not to generate generic content. Turn Michael's current reaction, experience, and recommendation into one credible LinkedIn post that strengthens his positioning with hiring managers, recruiters, consulting prospects, and influential practitioners.

VOICE PROFILE
{voice_profile}

PRIVATE EXPERIENCE CONTEXT
{experience_context}

NON-NEGOTIABLE RULES
- Michael's three inputs are the source of truth. The article is context, not the content.
- Do not invent facts, metrics, quotations, outcomes, or company details.
- Do not automatically insert a story from the private experience file.
- Use a named-company example only when Michael's current experience input clearly invokes it and the example is positive/public.
- Generalize setbacks and internal organizational problems.
- Do not position Michael as a MarTech, loyalty, lifecycle, or CRM-campaign leader.
- AI must be practical and non-hyped.
- Do not start with “I wanted to share,” “Great read,” or an article summary.
- Create one LinkedIn post, typically 140-230 words.
- Use short paragraphs and natural line breaks.
- A closing question is optional. When used, it must be specific and useful.
- Use no more than three specific hashtags, and omit them when they add no value.
- Return valid JSON only, with no markdown fence or explanation.
"""

    user_prompt = f"""ARTICLE CONTEXT
Title: {article.get('title', '')}
Source: {article.get('source', '')}
URL: {article.get('url', '')}
RSS excerpt: {article.get('summary', '')}

MICHAEL'S CURRENT INPUTS
Reaction — what stood out, and what he agrees or disagrees with:
{reaction}

Experience — what he has seen in practice:
{experience}

Recommendation — what leaders or teams should do differently:
{recommendation}

Return exactly:
{{"linkedin": "full post text"}}"""

    message = client.messages.create(
        model=POST_MODEL,
        max_tokens=1100,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())
    return result["linkedin"].strip()


# Backward-compatible wrapper for any external caller using the old function.
def generate_posts(article: dict, opinion: str) -> dict:
    post = generate_post(article, opinion, "", "")
    return {"linkedin": post}
