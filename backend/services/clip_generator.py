"""Everything that touches video: scene detection, timestamp validation, FFmpeg cutting/reframing.

Architecture rule: the LLM only *suggests* timestamps. This module validates and snaps them to real
sentence boundaries, then FFmpeg does the actual editing.
"""
import logging
import re
import subprocess
from pathlib import Path

from config import settings
from utils.file_utils import run_cmd

log = logging.getLogger("clips")


# ------------------------------------------------------------------ scene detection
def detect_scenes(video: Path, threshold: float = 0.35) -> list[float]:
    """Timestamps (seconds) where the picture changes a lot - slide change, IDE opened, outfit change..."""
    cmd = [settings.FFMPEG_BIN, "-hide_banner", "-nostats", "-i", str(video), "-an",
           "-vf", f"fps=2,scale=320:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    times = sorted(float(t) for t in re.findall(r"pts_time:([0-9.]+)", proc.stderr))
    out = []
    for t in times:
        if not out or t - out[-1] > 1.0:
            out.append(round(t, 2))
    return out


# ------------------------------------------------------------------ validation + ranking
def validate_and_rank(topics: list[dict], segments: list[dict], duration: float,
                      scenes: list[float], opts: dict) -> list[dict]:
    """Clamp, snap to sentence boundaries, enforce length, score, de-duplicate, pick the best N."""
    mn = float(opts["min_clip_seconds"])
    mx = max(float(opts["max_clip_seconds"]), mn + 5)
    starts = [s["start"] for s in segments]
    ends = [s["end"] for s in segments]
    cands = []

    for t in topics:
        try:
            s, e = float(t["start"]), float(t["end"])
        except (TypeError, ValueError, KeyError):
            continue
        if e <= s:
            continue
        s, e = max(0.0, min(s, duration)), max(0.0, min(e, duration))

        ns = min(starts, key=lambda x: abs(x - s))          # never start mid-sentence
        if abs(ns - s) <= 8:
            s = ns
        ne = min(ends, key=lambda x: abs(x - e))            # never stop mid-sentence
        if abs(ne - e) <= 8:
            e = ne

        if e - s > mx:
            ok = [x for x in ends if s + mn <= x <= s + mx]
            e = max(ok) if ok else s + mx
        if e - s < mn:
            ok = [x for x in ends if s + mn <= x <= s + mx]
            e = min(ok) if ok else min(duration, s + mn)
            if e - s < mn:
                s = max(0.0, e - mn)
        if e - s < 3:
            continue

        words = sum(len(g["text"].split()) for g in segments if g["end"] > s and g["start"] < e)
        energy = min(1.0, max(0.0, (words / (e - s) - 1.2) / 2.0))            # speaking pace proxy
        near = any(abs(sc - s) <= 3 for sc in scenes)
        inside = sum(1 for sc in scenes if s <= sc <= e)
        scene_boost = 1.0 if near else min(1.0, inside / 4) * 0.7
        importance = float(t.get("importance", 0.5))
        score = 0.65 * importance + 0.20 * energy + 0.15 * scene_boost

        c = dict(t)
        c.update(start=round(s, 2), end=round(e, 2), importance=importance,
                 energy=round(energy, 2), scene_boost=round(scene_boost, 2), score=round(score, 3))
        cands.append(c)

    chosen = []
    for c in sorted(cands, key=lambda x: -x["score"]):
        overlap = any(min(c["end"], k["end"]) - max(c["start"], k["start"]) > 0.3 * (c["end"] - c["start"])
                      for k in chosen)
        if not overlap:
            chosen.append(c)
        if len(chosen) >= opts["max_clips"]:
            break
    return sorted(chosen, key=lambda x: x["start"])


# ------------------------------------------------------------------ ffmpeg editing
def _graph(sw, sh, W, H, reframe: str) -> str:
    if sw and sh and abs(sw / sh - W / H) < 0.03:
        return f"[0:v]scale={W}:{H},setsar=1[v]"
    if reframe == "crop":
        return f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[v]"
    return (f"[0:v]split=2[a][b];"
            f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:4[bg];"
            f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2,setsar=1[v]")


def cut_video(src: Path, dst: Path, start: float, end: float, spec: dict, info: dict, reframe: str = "blur") -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    graph = _graph(info.get("width"), info.get("height"), spec["width"], spec["height"], reframe)
    run_cmd([settings.FFMPEG_BIN, "-y", "-ss", f"{start:.2f}", "-i", str(src), "-t", f"{end - start:.2f}",
             "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(dst)])


def make_thumbnail(src: Path, dst: Path, at: float) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    run_cmd([settings.FFMPEG_BIN, "-y", "-ss", f"{at:.2f}", "-i", str(src), "-frames:v", "1",
             "-vf", "scale=720:-2", "-q:v", "3", str(dst)])


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments: list[dict], start: float, end: float, dst: Path) -> bool:
    blocks, n = [], 1
    for s in segments:
        if s["end"] <= start or s["start"] >= end:
            continue
        a, b = max(s["start"], start) - start, min(s["end"], end) - start
        blocks.append(f"{n}\n{_srt_time(a)} --> {_srt_time(b)}\n{s['text']}\n")
        n += 1
    if not blocks:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(blocks), encoding="utf-8")
    return True
