"""
fetch_articles.py
Maintains a queue where EVERY article is guaranteed < MAX_AGE_DAYS old.

Freshness is enforced two ways:
1. At fetch: only articles with a parseable publish date within the window are
   admitted. Dateless / unparseable items are rejected (can't prove they're
   fresh, so we don't trust them).
2. Continuously: prune_stale() drops items that have aged past the window. The
   app calls this on every load (cheap, no network), so a stale item can never
   be shown even if it was admitted when it was fresh.

topup_queue() refills to the target size and prunes defensively first.
history is a capped rolling dedup list of every URL ever surfaced.
"""

import feedparser
import json
import re
import hashlib
import sys
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "sources.json"
STATE_PATH = ROOT / "state.json"

# Tunables (override via config["queue"])
TARGET_QUEUE_SIZE = 12     # top up to this many
MIN_QUEUE_SIZE = 5         # app triggers a network top-up when below this
DEFAULT_MAX_AGE_DAYS = 2   # hard freshness ceiling
HISTORY_CAP = 250

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def load_state():
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"queue": [], "history": [], "generated_at": None}

def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()

def article_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]

def _max_age(max_age_days):
    if max_age_days is not None:
        return max_age_days
    return load_config().get("queue", {}).get("max_age_days", DEFAULT_MAX_AGE_DAYS)

def parse_published(entry):
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    for key in ("published", "updated"):
        raw = entry.get(key)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass
    return None

def _parse_iso(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def score_article(title, summary, config):
    text = (title + " " + summary).lower()
    score = 0
    keywords = config["keywords"]
    weights = config["scoring"]
    for kw in keywords["exclude"]:
        if kw.lower() in text:
            score += weights["exclude_penalty"]
    for kw in keywords["high_value"]:
        if kw.lower() in text:
            score += weights["high_value_weight"]
    for kw in keywords["medium_value"]:
        if kw.lower() in text:
            score += weights["medium_value_weight"]
    return score

# ── Freshness ─────────────────────────────────────────────────────────────────

def prune_stale(queue, max_age_days=None):
    """Drop queue items older than the window or lacking a valid date.
    Pure / no network — safe to call on every page load."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=_max_age(max_age_days))
    fresh = []
    for a in queue or []:
        dt = _parse_iso(a.get("published"))
        if dt is not None and dt >= cutoff:
            fresh.append(a)
    return fresh

# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_candidates(config, exclude_urls, max_age_days=None):
    """Qualifying articles strictly within the freshness window, ranked by
    score then recency, excluding any URL in exclude_urls."""
    max_age_days = _max_age(max_age_days)
    min_score = config["scoring"]["min_score_threshold"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    exclude = set(exclude_urls)
    seen_this_run = set()
    candidates = []

    for feed_info in config["feeds"]:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:25]:
                url = entry.get("link", "")
                if not url or url in exclude or url in seen_this_run:
                    continue
                published = parse_published(entry)
                # STRICT: require a verifiable date inside the window.
                if published is None or published < cutoff:
                    continue
                title = entry.get("title", "")
                summary = strip_html(entry.get("summary", ""))[:600]
                score = score_article(title, summary, config) * feed_info.get("weight", 1.0)
                if score < min_score:
                    continue
                seen_this_run.add(url)
                candidates.append({
                    "id": article_id(url),
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "source": feed_info["name"],
                    "score": round(score, 2),
                    "published": published.isoformat(),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            print(f"[WARN] Failed to parse {feed_info['name']}: {e}")

    candidates.sort(key=lambda x: (x["score"], x["published"]), reverse=True)
    return candidates


def topup_queue(current_queue, history, target_size=None, max_age_days=None):
    """Prune stale items, then append fresh ones until the queue reaches target.
    Returns (new_queue, new_history)."""
    config = load_config()
    target = target_size or config.get("queue", {}).get("size", TARGET_QUEUE_SIZE)

    current_queue = prune_stale(list(current_queue or []), max_age_days)  # defensive
    history = list(history or [])

    needed = target - len(current_queue)
    if needed <= 0:
        return current_queue, history

    exclude = set(history) | {a["url"] for a in current_queue}
    additions = fetch_candidates(config, exclude, max_age_days)[:needed]

    new_queue = current_queue + additions
    new_history = (history + [a["url"] for a in additions])[-HISTORY_CAP:]
    return new_queue, new_history

# ── GitHub Actions entrypoint (background warm-up) ────────────────────────────

def main():
    state = load_state()
    queue = state.get("queue", [])
    history = state.get("history", [])

    before = [a["url"] for a in queue]
    new_queue, new_history = topup_queue(queue, history)
    after = [a["url"] for a in new_queue]

    if after == before:
        print(f"[SKIP] No change. Queue holds {len(queue)} fresh articles.")
        sys.exit(0)

    state["queue"] = new_queue
    state["history"] = new_history
    state["generated_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    print(f"[OK] Queue now holds {len(new_queue)} fresh (<{_max_age(None)}d) articles.")
    for i, a in enumerate(new_queue, 1):
        print(f"  {i:>2}. [{a['score']:>5.1f}] {a['source']:<22} {a['title'][:70]}")
    print("[DONE] State updated.")

if __name__ == "__main__":
    main()
