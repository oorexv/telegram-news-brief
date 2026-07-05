import json
import os
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import feedparser
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

STATE_FILE = "state.json"

US_FEEDS = [
    ("BBC", "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"),
    ("NYT", "https://rss.nytimes.com/services/xml/rss/nyt/US.xml"),
    ("CNN", "http://rss.cnn.com/rss/cnn_us.rss"),
]
WORLD_FEEDS = [
    ("BBC", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("NYT", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("CNN", "http://rss.cnn.com/rss/cnn_world.rss"),
]

SCHEDULE_HOURS = [7, 11, 13, 15, 18, 21]
SCHEDULE_LABELS = ["7:00 AM", "11:00 AM", "1:00 PM", "3:00 PM", "6:00 PM", "9:00 PM"]


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = (
        text.replace("&amp;", "&")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
        .replace("&nbsp;", " ")
    )
    return text.strip()


def fetch_category(feeds, limit=3):
    entries = []
    for source, url in feeds:
        try:
            d = feedparser.parse(url)
        except Exception as e:
            print(f"Failed to fetch {source}: {e}")
            continue
        if getattr(d, "bozo", 0) and not d.entries:
            print(f"Warning: {source} feed had errors: {getattr(d, 'bozo_exception', '')}")
        for e in d.entries[:10]:
            title = clean_html(e.get("title", ""))
            link = e.get("link", "")
            summary = clean_html(e.get("summary", "") or e.get("description", ""))
            published = e.get("published_parsed")
            ts = datetime(*published[:6], tzinfo=timezone.utc) if published else None
            if title and link:
                entries.append(
                    {"title": title, "link": link, "summary": summary, "source": source, "ts": ts}
                )
    entries.sort(key=lambda x: x["ts"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    seen = set()
    unique = []
    for e in entries:
        key = re.sub(r"[^a-z0-9]", "", e["title"].lower())[:40]
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
        if len(unique) >= limit:
            break
    return unique


def et_now():
    return datetime.now(ZoneInfo("America/New_York"))


def next_time_label(now_et):
    cur_hour = now_et.hour
    for h, label in zip(SCHEDULE_HOURS, SCHEDULE_LABELS):
        if h > cur_hour:
            return label
    return SCHEDULE_LABELS[0]


def build_message(us_items, world_items, now_et):
    time_str = now_et.strftime("%-I:%M %p ET")
    lines = [f"\U0001F4F0 Oore's News Brief  •  {time_str}", ""]
    idx = 1
    for item in us_items:
        lines.append(f"\U0001F1FA\U0001F1F8 {idx}. {item['title']}")
        idx += 1
    if us_items and world_items:
        lines.append("")
    for item in world_items:
        lines.append(f"\U0001F30E {idx}. {item['title']}")
        idx += 1
    lines.append("")
    total = idx - 1
    nxt = next_time_label(now_et)
    lines.append(f"Reply 1–{total} for a summary  •  Next: {nxt}")
    return "\n".join(lines)


def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID env vars.")
        sys.exit(1)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": CHAT_ID, "text": text})
    resp.raise_for_status()
    print("Brief sent:", resp.json())


def main():
    now_et = et_now()
    us_items = fetch_category(US_FEEDS, limit=3)
    world_items = fetch_category(WORLD_FEEDS, limit=3)

    if not us_items and not world_items:
        print("No headlines fetched from any feed. Skipping send so we don't send an empty brief.")
        return

    message = build_message(us_items, world_items, now_et)
    send_telegram(message)

    items = {}
    n = 1
    for item in us_items + world_items:
        items[str(n)] = {
            "title": item["title"],
            "link": item["link"],
            "summary": item["summary"] or "(No summary available from the source feed.)",
            "source": item["source"],
        }
        n += 1

    state = {"sent_at": now_et.isoformat(), "items": items}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print(f"Wrote state.json with {len(items)} items")


if __name__ == "__main__":
    main()
