"""LLM analysis: transcript/document -> topics (with timestamps for media), titles, captions, hashtags.

Providers: Anthropic, OpenAI, Gemini. With no API key it falls back to a keyword/density heuristic
so the whole pipeline still runs (handy for demos and offline development).
"""
import collections
import json
import logging
import math
import re

import httpx

from config import settings

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


def _prompt_common(opts: dict) -> str:
    return (f"Writing tone: {TONE.get(opts.get('tone'), TONE['educational'])}.\n"
            f"Write titles, hooks, captions and key points in: {LANG.get(opts.get('language'), 'English')}.\n"
            "Hashtags must be relevant, mixed between broad and niche, and start with #.\n")


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
def analyze_document(text: str, units: list[dict], opts: dict) -> dict:
    if llm_enabled():
        try:
            prompt = (
                f"Below is a document. Find up to {opts['max_clips']} of the most valuable concepts that can each "
                "become a standalone social post / carousel. Do NOT include start/end timestamps (use 0).\n"
                f"{_prompt_common(opts)}\nReturn JSON in exactly this shape:\n{TOPIC_SCHEMA}\n\n"
                "DOCUMENT:\n" + text[:45000])
            data = ask_json(SYSTEM, prompt)
            topics = [normalize_topic(t) for t in data.get("topics", []) if isinstance(t, dict)]
            if topics:
                return {"summary": str(data.get("summary", "")), "keywords": [str(k) for k in data.get("keywords", [])][:15],
                        "topics": topics, "provider": settings.llm_provider(), "warning": None}
            raise ValueError("LLM returned no topics")
        except Exception as e:
            log.exception("LLM document analysis failed, using heuristic fallback")
            result = heuristic_analysis(units, opts, timed=False)
            result["warning"] = f"AI analysis failed ({type(e).__name__}); used the built-in keyword analyser instead."
            return result
    return heuristic_analysis(units, opts, timed=False)


# ------------------------------------------------------------------ heuristic fallback (no API key)
STOP = set("""a about above after again all also am an and any are as at be because been before being below between both
but by can could did do does doing down during each few for from further get got had has have having he her here hers him
his how i if in into is it its just let like me more most my no nor not now of off on once only or other our out over own
really same she should so some such than that the their them then there these they this those through to too under until up
very was we were what when where which while who why will with would you your yeah okay ok um uh going gonna want need
today next first second thing things one two three say said see look know right well make use used using""".split())

TECH = set("""python variable variables function functions data type types integer float string boolean list tuple dictionary
set loop loops class object objects oop array algorithm database sql api code program syntax operator conditional module
library javascript react html css git machine learning model neural network recursion inheritance exception file""".split())

CAPTIONS = {
    "educational": "A quick, clear explanation of {t}. Save this for revision! 📚",
    "genz": "{t}, but make it make sense ✨ no cap, this one's a lifesaver",
    "professional": "A concise breakdown of {t} - practical insights you can apply today.",
    "funny": "POV: you finally understand {t} 😭☕",
}
TITLES = ["{t} Explained Simply", "Understanding {t}", "{t} Made Easy", "Quick Guide to {t}", "{t}: What You Need to Know"]


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_+#]{2,}", text.lower()) if w not in STOP]


def _windows(units: list[dict], timed: bool, target: float) -> list[list[dict]]:
    wins, cur, acc = [], [], 0.0
    for u in units:
        cur.append(u)
        acc += (u["end"] - u["start"]) if timed else len(u["text"].split())
        if acc >= target:
            wins.append(cur)
            cur, acc = [], 0.0
    if cur:
        if wins and acc < target * 0.4:
            wins[-1].extend(cur)
        else:
            wins.append(cur)
    return wins


def _key_points(text: str, n: int = 3) -> list[str]:
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if 25 <= len(s.strip()) <= 220]
    sents = list(dict.fromkeys(sents))
    return sorted(sents[:8], key=len, reverse=True)[:n] if sents else []


def heuristic_analysis(units: list[dict], opts: dict, timed: bool) -> dict:
    full = " ".join(u["text"] for u in units)
    glob = collections.Counter(_tokens(full))
    target = (opts["min_clip_seconds"] + opts["max_clip_seconds"]) / 2 if timed else 90
    wins = _windows(units, timed, target)

    def weight(term):
        return 3 if term in TECH else 1

    scored = []
    for w in wins:
        text = " ".join(u["text"] for u in w)
        counts = collections.Counter(_tokens(text))
        words = max(1, len(text.split()))
        dens = sum(c * weight(t) for t, c in counts.items() if glob[t] >= 2) / words
        best = max(counts, key=lambda t: counts[t] * weight(t) * (1 + math.log(1 + glob[t])), default="this topic")
        scored.append((dens, best, w, text, counts))

    max_d = max((s[0] for s in scored), default=1) or 1
    tone = opts.get("tone", "educational")
    topics = []
    for i, (dens, term, w, text, counts) in enumerate(scored):
        label = term.upper() if len(term) <= 3 else term.capitalize()
        kws = [t for t, _ in counts.most_common(8) if glob[t] >= 2][:5]
        first = next((s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20), text[:90])
        topics.append({
            "topic": label,
            "title": TITLES[i % len(TITLES)].format(t=label),
            "hook": f"Still confused about {label}? {'Watch this.' if timed else 'Read this.'}",
            "caption": CAPTIONS.get(tone, CAPTIONS["educational"]).format(t=label),
            "hashtags": [f"#{label}"] + [f"#{k}" for k in kws],
            "keywords": kws,
            "key_points": _key_points(text) or [first[:120]],
            "importance": round(0.5 + 0.45 * (dens / max_d), 2),
            "start": w[0]["start"] if timed else None,
            "end": w[-1]["end"] if timed else None,
        })
    keywords = [t for t, _ in glob.most_common(40) if glob[t] >= 2]
    keywords = sorted(keywords, key=lambda t: -(glob[t] * weight(t)))[:12]
    summary = " ".join(re.split(r"(?<=[.!?])\s+", full)[:2])[:320]
    return {"summary": summary, "keywords": keywords, "topics": topics, "provider": "heuristic", "warning": None}
