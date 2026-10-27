"""File helpers, ffmpeg helpers and a tiny JSON-file job store."""
import json
import re
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile

from config import settings

EXT_KIND = {
    ".mp4": "video", ".mov": "video", ".mkv": "video", ".webm": "video",
    ".pdf": "document", ".docx": "document",
    ".txt": "text", ".md": "text",
}

_lock = threading.RLock()
_ID_RE = re.compile(r"^[a-f0-9]{12}$")


# ---------- basics ----------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def detect_kind(filename: str) -> str | None:
    return EXT_KIND.get(Path(filename or "").suffix.lower())


def upload_dir(job_id: str) -> Path:
    return settings.UPLOAD_DIR / job_id


def output_dir(job_id: str) -> Path:
    return settings.OUTPUT_DIR / job_id


def fmt_time(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def safe_join(base: Path, rel: str) -> Path:
    """Resolve rel inside base, refusing path traversal."""
    target = (base / rel).resolve()
    if base.resolve() not in target.parents and target != base.resolve():
        raise HTTPException(400, "Invalid path")
    return target


# ---------- uploads ----------
def save_upload(file: UploadFile, job_id: str) -> tuple[Path, int, str]:
    ext = Path(file.filename or "").suffix.lower()
    kind = EXT_KIND.get(ext)
    if not kind:
        raise HTTPException(415, f"Unsupported file type '{ext or '?'}'. Allowed: {', '.join(sorted(EXT_KIND))}")
    folder = upload_dir(job_id)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"original{ext}"
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    size, too_big = 0, False
    with open(dest, "wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                too_big = True
                break
            out.write(chunk)
    if too_big:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(413, f"File is larger than {settings.MAX_UPLOAD_MB} MB")
    return dest, size, kind


# ---------- ffmpeg ----------
def run_cmd(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-6:]
        raise RuntimeError("ffmpeg failed: " + " | ".join(tail))


def probe(path: Path) -> dict:
    cmd = [settings.FFPROBE_BIN, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except FileNotFoundError as e:
        raise RuntimeError("ffprobe/ffmpeg is not installed. Install FFmpeg and make sure it is on PATH.") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError("This file could not be read as media. Is it corrupted?") from e
    data = json.loads(out)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    return {
        "duration": float(data.get("format", {}).get("duration") or 0),
        "width": video.get("width") if video else None,
        "height": video.get("height") if video else None,
        "has_video": bool(video),
    }


# ---------- job store (one JSON file per project) ----------
def _job_file(job_id: str) -> Path:
    if not _ID_RE.match(job_id or ""):
        raise HTTPException(404, "Project not found")
    return upload_dir(job_id) / "job.json"


def save_job(job: dict) -> None:
    with _lock:
        path = _job_file(job["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)


def create_job(job_id: str, **fields) -> dict:
    job = {"id": job_id, "status": "uploaded", "stage": None, "progress": 0, "message": "",
           "error": None, "created_at": now_iso(), **fields}
    save_job(job)
    return job


def load_job(job_id: str) -> dict:
    path = _job_file(job_id)
    with _lock:
        if not path.exists():
            raise HTTPException(404, "Project not found")
        return json.loads(path.read_text(encoding="utf-8"))


def update_job(job_id: str, **fields) -> dict:
    with _lock:
        job = load_job(job_id)
        job.update(fields)
        save_job(job)
        return job


def list_jobs() -> list[dict]:
    jobs = []
    for f in settings.UPLOAD_DIR.glob("*/job.json"):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        jobs.append({k: j.get(k) for k in
                     ("id", "title", "filename", "kind", "status", "progress", "created_at", "stats", "platforms")})
    return sorted(jobs, key=lambda j: j.get("created_at") or "", reverse=True)


def delete_job(job_id: str) -> None:
    _job_file(job_id)
    shutil.rmtree(upload_dir(job_id), ignore_errors=True)
    shutil.rmtree(output_dir(job_id), ignore_errors=True)


def public_job(job: dict) -> dict:
    """Strip server-only fields before sending to the browser."""
    return {k: v for k, v in job.items() if k != "source_path"}
