from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from models.schemas import UrlUpload
from utils.file_utils import create_job, detect_kind, new_job_id, save_upload, upload_dir

router = APIRouter(tags=["upload"])


@router.post("/upload")
def upload(file: UploadFile = File(...)):
    job_id = new_job_id()
    path, size, kind = save_upload(file, job_id)
    create_job(job_id, filename=file.filename, kind=kind, size=size, source_path=str(path))
    return {"job_id": job_id, "filename": file.filename, "kind": kind, "size": size}


@router.post("/upload-url")
def upload_url(body: UrlUpload):
    """Download a public YouTube (or other yt-dlp supported) link as the project's source video."""
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Please paste a full link starting with https://")
    try:
        import yt_dlp
    except ImportError:
        raise HTTPException(501, "Link import needs yt-dlp. Run: pip install yt-dlp")

    job_id = new_job_id()
    folder = upload_dir(job_id)
    folder.mkdir(parents=True, exist_ok=True)
    opts = {"format": "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b[height<=720]/b",
            "outtmpl": str(folder / "original.%(ext)s"), "merge_output_format": "mp4",
            "noplaylist": True, "quiet": True, "no_warnings": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        raise HTTPException(400, f"Couldn't download that link: {str(e)[:200]}")
    files = [f for f in folder.glob("original.*")]
    if not files:
        raise HTTPException(400, "Download finished but no file was produced.")
    path = files[0]
    title = (info or {}).get("title") or "YouTube video"
    create_job(job_id, filename=f"{title}{path.suffix}", kind=detect_kind(path.name) or "video",
               size=path.stat().st_size, source_path=str(path), source_url=url)
    return {"job_id": job_id, "filename": title, "kind": "video", "size": path.stat().st_size}
