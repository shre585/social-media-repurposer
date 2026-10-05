"""The orchestrator:  input -> text/transcript -> LLM topics -> validated timestamps -> FFmpeg -> platform content."""
import logging
import re
import threading
from pathlib import Path

from config import settings
from services import clip_generator as cg
from services.content_generator import build_carousel, build_chapters, generate_extras
from services.llm_analysis import analyze_document, analyze_transcript, normalize_topic
from services.platform_formatter import DEFAULT_PLATFORMS, PLATFORMS, format_content
from services.text_processor import read_document, to_units
from services.transcription import extract_audio, transcribe
from utils.file_utils import load_job, output_dir, probe, update_job

log = logging.getLogger("pipeline")
_slots = threading.Semaphore(settings.MAX_CONCURRENT_JOBS)

MEDIA_STEPS = [("extract", "Extracting audio"), ("transcribe", "Transcribing speech"),
               ("analyze", "Finding key topics"), ("scenes", "Detecting scene changes"),
               ("clips", "Cutting & reframing clips"), ("content", "Writing captions & hashtags"),
               ("finalize", "Packaging results")]
DOC_STEPS = [("extract", "Reading your document"), ("analyze", "Finding key concepts"),
             ("content", "Writing posts & carousels"), ("finalize", "Packaging results")]


def _stage(job_id, stage, progress, message):
    update_job(job_id, stage=stage, progress=progress, message=message)


def _steps(kind):
    steps = DOC_STEPS if kind in ("document", "text") else MEDIA_STEPS
    if kind == "audio":
        steps = [s for s in steps if s[0] != "scenes"]
    return [{"id": i, "label": l} for i, l in steps]


def _pretty_title(filename: str) -> str:
    stem = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", filename or "Untitled")
    return re.sub(r"[_\-]+", " ", stem).strip().title() or "Untitled"


def run_pipeline(job_id: str, options: dict) -> None:
    with _slots:
        try:
            _run(job_id, options)
        except Exception as e:
            log.exception("Pipeline failed for %s", job_id)
            update_job(job_id, status="failed", error=str(e), message="Something went wrong")


def _run(job_id: str, opts: dict) -> None:
    job = load_job(job_id)
    kind, src = job["kind"], Path(job["source_path"])
    platforms = [p for p in opts["platforms"] if p in PLATFORMS] or DEFAULT_PLATFORMS
    opts["platforms"] = platforms
    title = _pretty_title(job.get("filename"))
    update_job(job_id, status="processing", steps=_steps(kind), options=opts, platforms=platforms,
               title=title, error=None, progress=2, stage=_steps(kind)[0]["id"], message="Starting…")
    out = output_dir(job_id)
    out.mkdir(parents=True, exist_ok=True)

    def url(rel):
        return f"/files/{job_id}/{rel}"

    def dl(rel):
        return f"/api/download/{job_id}/{rel}"

    items, segments, duration = [], [], 0.0

    if kind in ("video", "audio"):
        info = probe(src)
        duration = info["duration"]
        _stage(job_id, "extract", 5, "Pulling the audio track out…")
        wav = out / "audio.wav"
        extract_audio(src, wav)

        _stage(job_id, "transcribe", 12, "Listening carefully (this is the slow part)…")
        segments, lang = transcribe(wav)
        if not segments:
            raise RuntimeError("No speech was detected in this file.")
        update_job(job_id, transcript=segments, detected_language=lang, duration=duration)

        _stage(job_id, "analyze", 40, "Reading the transcript for key concepts…")
        analysis = analyze_transcript(segments, opts)

        scenes = []
        if kind == "video":
            _stage(job_id, "scenes", 52, "Looking for slide changes and cuts…")
            try:
                scenes = cg.detect_scenes(src)
            except Exception:
                log.exception("Scene detection failed (continuing without it)")

        topics = cg.validate_and_rank(analysis["topics"], segments, duration, scenes, opts)
        if not topics:
            raise RuntimeError("Couldn't find any usable moments. Try a longer file or shorter minimum clip length.")

        _stage(job_id, "clips", 58, f"Cutting {len(topics)} clips…")
        for n, t in enumerate(topics):
            cid = f"c{n + 1}"
            item = _base_item(cid, t)
            item["duration"] = round(t["end"] - t["start"], 1)
            base = Path("clips") / cid
            try:
                if kind == "video":
                    cg.make_thumbnail(src, out / base / "thumb.jpg", t["start"] + (t["end"] - t["start"]) / 3)
                    item["thumbnail"] = url(f"{base}/thumb.jpg")
                else:
                    cg.cut_audio(src, out / base / "clip.mp3", t["start"], t["end"])
                    item["audio"] = {"url": url(f"{base}/clip.mp3"), "download": dl(f"{base}/clip.mp3")}
                if cg.write_srt(segments, t["start"], t["end"], out / base / "captions.srt"):
                    item["srt"] = {"download": dl(f"{base}/captions.srt")}
            except Exception:
                log.exception("Thumbnail/audio/srt failed for %s", cid)

            for pid in platforms:
                spec = PLATFORMS[pid]
                end = min(t["end"], t["start"] + spec["max_seconds"])
                entry = _platform_entry(spec, format_content(t, pid, opts["tone"]))
                rel = f"{base}/{pid}.mp4"
                try:
                    if kind == "video":
                        cg.cut_video(src, out / rel, t["start"], end, spec, info, opts["reframe"])
                    else:
                        cg.make_audiogram(src, out / rel, t["start"], end, spec)
                    entry["media"] = {"url": url(rel), "download": dl(rel), "type": "video",
                                      "width": spec["width"], "height": spec["height"],
                                      "duration": round(end - t["start"], 1), "trimmed": end < t["end"]}
                except Exception as e:
                    log.exception("Cut failed for %s/%s", cid, pid)
                    entry["media_error"] = str(e)[:300]
                item["platforms"][pid] = entry
            items.append(item)
            _stage(job_id, "clips", 58 + int(32 * (n + 1) / len(topics)), f"Finished clip {n + 1} of {len(topics)}")
        wav.unlink(missing_ok=True)
    else:
        _stage(job_id, "extract", 8, "Reading your document…")
        text = read_document(src)
        units = to_units(text)
        _stage(job_id, "analyze", 30, "Finding the concepts worth posting…")
        analysis = analyze_document(text, units, opts)
        topics = [normalize_topic(t) for t in analysis["topics"]][: opts["max_clips"]]
        topics.sort(key=lambda t: -t["importance"])
        _stage(job_id, "content", 65, "Writing posts and carousels…")
        for n, t in enumerate(topics):
            item = _base_item(f"c{n + 1}", t)
            for pid in platforms:
                item["platforms"][pid] = _platform_entry(PLATFORMS[pid], format_content(t, pid, opts["tone"]))
            items.append(item)

    _stage(job_id, "content", 92, "Writing the blog, thread and SEO bits…")
    extras = generate_extras(title, analysis, items, opts)
    extras["chapters"] = build_chapters(items)

    _stage(job_id, "finalize", 98, "Packaging everything…")
    update_job(
        job_id, status="completed", stage="finalize", progress=100, message="Ready!",
        clips=items, extras=extras, summary=analysis.get("summary", ""), keywords=analysis.get("keywords", []),
        provider=analysis.get("provider"), warning=analysis.get("warning"),
        stats={"topics": len(analysis["topics"]), "clips": len(items), "platforms": len(platforms),
               "duration": round(duration, 1)})


def _base_item(cid: str, t: dict) -> dict:
    return {"id": cid, "topic": t["topic"], "title": t["title"], "hook": t.get("hook", ""),
            "keywords": t.get("keywords", []), "key_points": t.get("key_points", []),
            "importance": round(t.get("importance", 0.5), 2), "score": t.get("score"),
            "start": t.get("start"), "end": t.get("end"), "duration": None,
            "carousel": build_carousel(t), "thumbnail": None, "srt": None, "audio": None, "platforms": {}}


def _platform_entry(spec: dict, content: dict) -> dict:
    return {"label": spec["label"], "emoji": spec["emoji"], "aspect": spec["aspect"],
            "best_time": spec["best_times"], "tip": spec["tip"], "content": content, "media": None}
