"""Content that goes beyond one clip: carousels, YouTube chapters, blog, X thread, LinkedIn post, SEO."""
import logging

from services import llm_analysis as llm
from services.platform_formatter import truncate
from utils.file_utils import fmt_time

log = logging.getLogger("content")


def build_carousel(topic: dict) -> list[dict]:
    """Instagram/LinkedIn carousel slides: hook -> key points -> call to action."""
    slides = [{"title": topic["title"], "body": topic.get("hook") or topic["topic"]}]
    for i, p in enumerate(topic.get("key_points", [])[:5], 1):
        slides.append({"title": f"#{i}", "body": truncate(p, 140)})
    slides.append({"title": "Enjoyed this?", "body": "Save it 📌  Share it 🔁  Follow for more"})
    return slides


def build_chapters(items: list[dict]) -> str:
    timed = sorted((i for i in items if i.get("start") is not None), key=lambda i: i["start"])
    if not timed:
        return ""
    lines = [f"{fmt_time(i['start'])} {i['title']}" for i in timed]
    if not lines[0].startswith("00:00"):
        lines.insert(0, "00:00 Intro")
    return "\n".join(lines)


def _fallback_extras(title: str, analysis: dict, items: list[dict], opts: dict) -> dict:
    summary = analysis.get("summary") or f"Key ideas from {title}."
    kws = analysis.get("keywords", [])
    blog = [f"# {title}", "", summary, ""]
    for it in items:
        blog += [f"## {it['title']}", ""] + [f"- {p}" for p in it.get("key_points", [])] + [""]
    thread = [truncate(f"🧵 {title}: {len(items)} things worth knowing. (1/{len(items) + 2})", 275)]
    for n, it in enumerate(items, 2):
        pt = (it.get("key_points") or [it["topic"]])[0]
        thread.append(truncate(f"{n}/ {it['title']} - {pt}", 275))
    thread.append(truncate(f"{len(items) + 2}/ That's a wrap. Follow for more bite-sized lessons ☕", 275))
    linkedin = f"{title}\n\n{summary}\n\n" + "\n".join(f"• {it['title']}" for it in items) + \
               "\n\nWhich of these would you like me to go deeper on? 👇"
    return {
        "blog_markdown": "\n".join(blog),
        "x_thread": thread,
        "linkedin_post": linkedin,
        "seo_title": truncate(f"{title} - Explained Simply", 60),
        "meta_description": truncate(summary, 155),
        "seo_keywords": kws[:10],
    }


def generate_extras(title: str, analysis: dict, items: list[dict], opts: dict) -> dict:
    fallback = _fallback_extras(title, analysis, items, opts)
    if not llm.llm_enabled():
        return fallback
    try:
        outline = "\n".join(f"- {it['title']}: " + "; ".join(it.get("key_points", [])) for it in items)
        prompt = (
            f"Project title: {title}\nSummary: {analysis.get('summary', '')}\nTopics:\n{outline}\n\n"
            f"{llm._prompt_common(opts)}\n"
            "Write repurposed content as JSON with exactly these keys: "
            '{"blog_markdown": "a 350-500 word blog post in markdown with H2 sections", '
            '"x_thread": ["tweet 1 (max 270 chars, with hook)", "..."], '
            '"linkedin_post": "a 150-200 word LinkedIn post ending with a question", '
            '"seo_title": "max 60 chars", "meta_description": "max 155 chars", "seo_keywords": ["..."]}')
        data = llm.ask_json(llm.SYSTEM, prompt, max_tokens=3500)
        out = dict(fallback)
        for k in fallback:
            if data.get(k):
                out[k] = data[k]
        out["x_thread"] = [truncate(str(t), 275) for t in out["x_thread"]][:12]
        return out
    except Exception:
        log.exception("Extras generation failed - using templates")
        return fallback
