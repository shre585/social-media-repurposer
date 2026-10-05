"""Per-platform rules: aspect ratio, resolution, max length, caption/hashtag/title limits."""
import re

PLATFORMS: dict[str, dict] = {
    "instagram": dict(
        id="instagram", label="Instagram Reels", short="Instagram", emoji="📸", aspect="9:16",
        width=1080, height=1920, max_seconds=90, caption_limit=2200, hashtag_limit=10,
        best_times=["Tue-Thu, 7-9 PM", "Sat, 11 AM"], tip="Hook viewers in the first 3 seconds."),
    "youtube": dict(
        id="youtube", label="YouTube Shorts", short="YouTube Shorts", emoji="▶️", aspect="9:16",
        width=1080, height=1920, max_seconds=60, caption_limit=5000, hashtag_limit=5, title_limit=100,
        best_times=["Fri-Sun, 12-3 PM", "Daily, 6-8 PM"], tip="Keep it under 60s and loop-friendly."),
    "youtube_long": dict(
        id="youtube_long", label="YouTube Video", short="YouTube", emoji="🎞️", aspect="16:9",
        width=1920, height=1080, max_seconds=3600, caption_limit=5000, hashtag_limit=3, title_limit=100,
        best_times=["Thu-Fri, 2-4 PM", "Sat, 9-11 AM"], tip="Put the keyword in the first 60 characters of the title."),
    "facebook": dict(
        id="facebook", label="Facebook", short="Facebook", emoji="👥", aspect="4:5",
        width=1080, height=1350, max_seconds=120, caption_limit=2000, hashtag_limit=3,
        best_times=["Wed-Fri, 1-4 PM"], tip="Square-ish video takes more feed space on mobile."),
    "x": dict(
        id="x", label="X (Twitter)", short="X", emoji="🐦", aspect="16:9",
        width=1280, height=720, max_seconds=140, caption_limit=280, hashtag_limit=2,
        best_times=["Mon-Fri, 8-10 AM", "Wed, 12 PM"], tip="Short text + one strong hashtag works best."),
    "snapchat": dict(
        id="snapchat", label="Snapchat Spotlight", short="Snapchat", emoji="👻", aspect="9:16",
        width=1080, height=1920, max_seconds=60, caption_limit=80, hashtag_limit=3,
        best_times=["Daily, 9-11 PM"], tip="Vertical, fast cuts, big text."),
    "linkedin": dict(
        id="linkedin", label="LinkedIn", short="LinkedIn", emoji="💼", aspect="1:1",
        width=1080, height=1080, max_seconds=120, caption_limit=3000, hashtag_limit=4,
        best_times=["Tue-Thu, 8-10 AM"], tip="Lead with a takeaway, end with a question."),
}
DEFAULT_PLATFORMS = ["instagram", "youtube"]

GENERIC_TAGS = ["Learning", "Education", "Explained", "Tutorial", "Tips", "HowTo", "Trending"]
CTA = {
    "educational": "Save this for later 📌 and follow for more!",
    "genz": "Save it, send it to your study buddy 🫶",
    "professional": "Follow for more practical insights.",
    "funny": "Follow so you don't get lost next time 😭",
}


def truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if limit <= 0 or len(text) <= limit:
        return text
    cut = text[: max(1, limit - 1)]
    if " " in cut[int(limit * 0.6):]:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:-") + "…"


def clean_tag(raw: str) -> str:
    words = re.sub(r"[^\w\s]", " ", str(raw).replace("#", " ")).split()
    word = "".join(w if w[:1].isupper() else w.capitalize() for w in words)
    return f"#{word}" if word else ""


def normalize_tags(tags: list[str], keywords: list[str] | None = None, minimum: int = 5) -> list[str]:
    seen, out = set(), []
    for raw in list(tags or []) + list(keywords or []):
        t = clean_tag(raw)
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    for g in GENERIC_TAGS:
        if len(out) >= minimum:
            break
        t = clean_tag(g)
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def compose(pid: str, title: str, caption: str, hashtags: list[str], tone: str = "educational") -> dict:
    """Build the final copy-paste text for a platform from title/caption/hashtags."""
    spec = PLATFORMS[pid]
    tags = [t if t.startswith("#") else clean_tag(t) for t in hashtags if t]
    tags = tags[: spec["hashtag_limit"]]
    tag_str = " ".join(tags)
    description = None

    if pid == "instagram":
        text = f"{caption}\n\n{CTA.get(tone, CTA['educational'])}\n\n{tag_str}"
    elif pid in ("youtube", "youtube_long"):
        extra = " #Shorts" if pid == "youtube" and "#shorts" not in tag_str.lower() else ""
        description = f"{caption}\n\n{tag_str}{extra}".strip()
        text = f"{truncate(title, spec['title_limit'])}\n\n{description}"
    elif pid == "x":
        room = spec["caption_limit"] - len(tag_str) - 2
        text = f"{truncate(caption, room)}\n\n{tag_str}".strip()
    elif pid == "snapchat":
        text = f"{truncate(caption, spec['caption_limit'])} {tag_str}".strip()
    elif pid == "linkedin":
        text = f"{caption}\n\nWhat would you add? 👇\n\n{tag_str}"
    else:  # facebook
        text = f"{caption}\n\n{tag_str}"

    if pid not in ("x", "snapchat"):
        text = truncate(text, spec["caption_limit"] + (spec.get("title_limit", 0) or 0))
    return {"text": text.strip(), "description": description}


def format_content(topic: dict, pid: str, tone: str = "educational") -> dict:
    """Adapt one analysed topic to a platform. Returns editable fields + final text."""
    spec = PLATFORMS[pid]
    title = truncate(topic.get("title") or topic.get("topic") or "Untitled", spec.get("title_limit") or 120)
    caption = (topic.get("caption") or "").strip()
    hook = (topic.get("hook") or "").strip()
    points = topic.get("key_points") or []

    if pid in ("instagram", "linkedin", "facebook") and hook and hook.lower() not in caption.lower():
        caption = f"{hook}\n\n{caption}".strip()
    if pid in ("linkedin", "youtube_long") and points:
        bullets = "\n".join(f"• {p}" for p in points[:4])
        caption = f"{caption}\n\n{bullets}".strip()
    if pid == "snapchat":
        caption = hook or caption

    tags = normalize_tags(topic.get("hashtags", []), topic.get("keywords", []))[: spec["hashtag_limit"]]
    built = compose(pid, title, caption, tags, tone)
    return {
        "title": title,
        "caption": caption,
        "hashtags": tags,
        "description": built["description"],
        "text": built["text"],
        "char_limit": spec["caption_limit"],
    }
