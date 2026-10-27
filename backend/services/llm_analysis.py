"""LLM analysis: transcript/document -> topics (with timestamps for media), titles, captions, hashtags.

Providers: Anthropic, OpenAI, Gemini. With no API key it falls back to a keyword/density heuristic
so the whole pipeline still runs (handy for demos and offline development).
"""
import json
import logging
import math
import re

import httpx

from config import settings
from services import topic_engine

log = logging.getLogger("llm")

LANG = {
    "english": "English",
    "hinglish": "Hinglish (Hindi written in Roman script, mixed with English)",
    "hindi": "Hindi (Devanagari script)",
}
TONE = {
    "educational": "clear, friendly and teacher-like",
    "genz": "fun, casual Gen-Z voice with light slang and a few emojis",
    "professional": "polished, concise and professional",
    "funny": "witty, playful and a little meme-y",
}
SYSTEM = (
    "You are a senior short-form content strategist who turns educational material into viral-ready posts. "
    "You always answer with ONE valid JSON object and nothing else - no markdown fences, no commentary."
)

TOPIC_SCHEMA = (
    '{"summary": "2 sentence summary", "keywords": ["main keywords"], "topics": [{'
    '"topic": "short topic name", "start": 0.0, "end": 0.0, "importance": 0.0, '
    '"title": "catchy title under 70 chars", "hook": "first-line hook under 100 chars", '
    '"caption": "2-3 sentence caption", "hashtags": ["#Tag1", "#Tag2"], '
    '"keywords": ["kw"], "key_points": ["3-5 short bullet points a viewer learns"]}]}'
)


# ------------------------------------------------------------------ LLM plumbing
def call_llm(system: str, user: str, max_tokens: int = 4096) -> str:
    provider = settings.llm_provider()
    timeout = httpx.Timeout(180.0, connect=15.0)
    if provider == "anthropic":
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": settings.ANTHROPIC_MODEL, "max_tokens": max_tokens, "system": system,
                  "messages": [{"role": "user", "content": user}]},
            timeout=timeout)
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    if provider == "openai":
        r = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={"model": settings.OPENAI_MODEL, "max_tokens": max_tokens,
                  "response_format": {"type": "json_object"},
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            timeout=timeout)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    if provider == "gemini":
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": settings.GEMINI_API_KEY},
            json={"systemInstruction": {"parts": [{"text": system}]},
                  "contents": [{"role": "user", "parts": [{"text": user}]}],
                  "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": max_tokens}},
            timeout=timeout)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    raise RuntimeError("No LLM configured")


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        raise ValueError("LLM did not return JSON")
    return json.loads(text[a:b + 1])


def ask_json(system: str, user: str, max_tokens: int = 4096) -> dict:
    last = None
    for attempt in range(2):
        try:
            return parse_json(call_llm(system, user, max_tokens))
        except Exception as e:  # network error, bad JSON, rate limit...
            last = e
            log.warning("LLM attempt %s failed: %s", attempt + 1, e)
    raise last


def llm_enabled() -> bool:
    return settings.llm_provider() != "mock"


# ------------------------------------------------------------------ normalisation
def _clamp(v, lo=0.0, hi=1.0):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return 0.5


def normalize_topic(t: dict) -> dict:
    topic = str(t.get("topic") or t.get("title") or "Untitled topic").strip()
    return {
        "topic": topic,
        "title": str(t.get("title") or topic).strip(),
        "hook": str(t.get("hook") or "").strip(),
        "caption": str(t.get("caption") or "").strip(),
        "hashtags": [str(h) for h in (t.get("hashtags") or []) if h][:15],
        "keywords": [str(k) for k in (t.get("keywords") or []) if k][:10],
        "key_points": [str(p).strip() for p in (t.get("key_points") or []) if str(p).strip()][:6],
        "importance": _clamp(t.get("importance", 0.5)),
        "start": t.get("start"),
        "end": t.get("end"),
    }


TOPIC_RULES = (
    "TOPIC RULES (very important):\n"
    "- Split the content by TEACHING CONCEPT, one topic per distinct concept, in the order it is taught. "
    "Example for a Python lecture: Variables, Data Types, Conditionals, Loops, Functions, Lists.\n"
    "- 'topic' must be the concept name (e.g. 'Variables', 'Data Types', 'Functions'), never generic words like "
    "'Introduction', 'Tutorial', 'Video' or 'Python Course'.\n"
    "- If the speaker explains a concept and then shows an example, make the example its own topic "
    "(e.g. 'Variables - example') when it is long enough.\n"
    "- 'keywords' = 4-6 terms specific to THAT topic only (for 'Variables': variable, assignment, naming rules, "
    "data stored, reassign). Do not repeat the same keywords across topics, and never use filler words.\n"
    "- Hashtags must be about the concept (e.g. #PythonVariables) plus the subject (#Python, #Coding).\n")


def _prompt_common(opts: dict) -> str:
    return (f"Writing tone: {TONE.get(opts.get('tone'), TONE['educational'])}.\n"
            f"Write titles, hooks, captions and key points in: {LANG.get(opts.get('language'), 'English')}.\n"
            "Hashtags must be relevant, mixed between broad and niche, and start with #.\n" + TOPIC_RULES)


# ------------------------------------------------------------------ media (transcript) analysis
def _lines(segments):
    return [f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in segments]


def _chunks(lines, limit=16000):
    chunks, cur, size = [], [], 0
    for ln in lines:
        if size + len(ln) > limit and cur:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(ln)
        size += len(ln) + 1
    if cur:
        chunks.append(cur)
    return chunks


def analyze_transcript(segments: list[dict], opts: dict) -> dict:
    if llm_enabled():
        try:
            chunks = _chunks(_lines(segments))
            per_chunk = max(2, math.ceil(opts["max_clips"] * 1.5 / len(chunks)))
            topics, summary, keywords = [], "", []
            for chunk in chunks:
                prompt = (
                    f"Below is a timestamped transcript ([start-end] in seconds). Find up to {per_chunk} of the best "
                    "self-contained moments that would work as standalone short videos.\n"
                    f"Rules: each moment starts where a thought begins and ends where it finishes; length between "
                    f"{opts['min_clip_seconds']} and {opts['max_clip_seconds']} seconds; use ONLY timestamps that "
                    "appear in the transcript; moments must not overlap; prefer concrete concepts "
                    "(e.g. variables, data types, functions) over small talk or intros.\n"
                    f"{_prompt_common(opts)}\nReturn JSON in exactly this shape:\n{TOPIC_SCHEMA}\n\n"
                    "TRANSCRIPT:\n" + "\n".join(chunk))
                data = ask_json(SYSTEM, prompt)
                summary = summary or str(data.get("summary", ""))
                keywords += [str(k) for k in data.get("keywords", [])]
                topics += [normalize_topic(t) for t in data.get("topics", []) if isinstance(t, dict)]
            if topics:
                _fill_keywords(topics, segments, None)
                return {"summary": summary, "keywords": list(dict.fromkeys(keywords))[:15],
                        "topics": topics, "provider": settings.llm_provider(), "warning": None}
            raise ValueError("LLM returned no topics")
        except Exception as e:
            log.exception("LLM analysis failed, using heuristic fallback")
            result = heuristic_analysis(segments, opts, timed=True)
            result["warning"] = f"AI analysis failed ({type(e).__name__}); used the built-in keyword analyser instead."
            return result
    return heuristic_analysis(segments, opts, timed=True)


# ------------------------------------------------------------------ document analysis
def _text_chunks(text: str, limit: int = 30000) -> list[str]:
    paras, chunks, cur, size = re.split(r"\n\s*\n", text), [], [], 0
    for p in paras:
        if size + len(p) > limit and cur:
            chunks.append("\n\n".join(cur))
            cur, size = [], 0
        cur.append(p)
        size += len(p) + 2
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


def analyze_document(text: str, units: list[dict], opts: dict) -> dict:
    if llm_enabled():
        try:
            chunks = _text_chunks(text)
            per_chunk = max(2, math.ceil(opts["max_clips"] * 1.5 / len(chunks)))
            topics, summary, keywords = [], "", []
            for chunk in chunks:
                prompt = (
                    f"Below is a document. Find up to {per_chunk} of the most valuable concepts that can each "
                    "become a standalone social post / carousel. Follow the document's own headings and sections "
                    "when it has them. Do NOT include start/end timestamps (use 0).\n"
                    f"{_prompt_common(opts)}\nReturn JSON in exactly this shape:\n{TOPIC_SCHEMA}\n\n"
                    "DOCUMENT:\n" + chunk)
                data = ask_json(SYSTEM, prompt)
                summary = summary or str(data.get("summary", ""))
                keywords += [str(k) for k in data.get("keywords", [])]
                topics += [normalize_topic(t) for t in data.get("topics", []) if isinstance(t, dict)]
            if topics:
                _fill_keywords(topics, None, text)
                return {"summary": summary, "keywords": list(dict.fromkeys(keywords))[:15],
                        "topics": topics, "provider": settings.llm_provider(), "warning": None}
            raise ValueError("LLM returned no topics")
        except Exception as e:
            log.exception("LLM document analysis failed, using heuristic fallback")
            result = heuristic_analysis(units, opts, timed=False, text=text)
            result["warning"] = f"AI analysis failed ({type(e).__name__}); used the built-in keyword analyser instead."
            return result
    return heuristic_analysis(units, opts, timed=False, text=text)


# ------------------------------------------------------------------ heuristic fallback (no API key)
def heuristic_analysis(units: list[dict], opts: dict, timed: bool, text: str | None = None) -> dict:
    """Built-in concept/keyword analyser (see services/topic_engine.py) - works offline, no API key."""
    result = topic_engine.analyze(units, opts, timed, text=text)
    result["topics"] = [normalize_topic(t) for t in result["topics"]]
    return result


def _fill_keywords(topics: list[dict], segments: list[dict] | None, text: str | None) -> None:
    """If the LLM returned thin keywords for a topic, add topic-specific ones from the lexicon / key-phrases."""
    for t in topics:
        if len(t["keywords"]) >= 4:
            continue
        if segments and t.get("start") is not None and t.get("end") is not None:
            body = " ".join(s["text"] for s in segments if s["end"] > t["start"] and s["start"] < t["end"])
        else:
            body = f"{t['topic']}. {t['title']}. " + " ".join(t.get("key_points", []))
        for k in topic_engine.suggest_keywords(body):
            if k.lower() not in [x.lower() for x in t["keywords"]]:
                t["keywords"].append(k)
        t["keywords"] = t["keywords"][:8]
