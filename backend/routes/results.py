import io
import zipfile

from fastapi import APIRouter
from fastapi.responses import FileResponse, StreamingResponse

from models.schemas import ContentUpdate
from services.platform_formatter import clean_tag, compose
from fastapi import HTTPException
from utils.file_utils import (delete_job, list_jobs, load_job, output_dir, public_job, safe_join,
                              save_job)

router = APIRouter(tags=["results"])


@router.get("/jobs")
def jobs():
    return {"jobs": list_jobs()}


@router.get("/results/{job_id}")
def results(job_id: str):
    return public_job(load_job(job_id))


@router.delete("/results/{job_id}")
def remove(job_id: str):
    delete_job(job_id)
    return {"deleted": job_id}


@router.put("/results/{job_id}/clips/{clip_id}/{platform}")
def update_content(job_id: str, clip_id: str, platform: str, body: ContentUpdate):
    """Save the user's edits to a title / caption / hashtags and rebuild the final post text."""
    job = load_job(job_id)
    clip = next((c for c in job.get("clips", []) if c["id"] == clip_id), None)
    if not clip or platform not in clip["platforms"]:
        raise HTTPException(404, "Clip or platform not found")
    content = clip["platforms"][platform]["content"]
    if body.title is not None:
        content["title"] = body.title.strip()
    if body.caption is not None:
        content["caption"] = body.caption.strip()
    if body.hashtags is not None:
        content["hashtags"] = [t for t in (clean_tag(h) for h in body.hashtags) if t]
    built = compose(platform, content["title"], content["caption"], content["hashtags"],
                    (job.get("options") or {}).get("tone", "educational"))
    content["text"], content["description"] = built["text"], built["description"]
    save_job(job)
    return content


@router.get("/download/{job_id}/{path:path}")
def download(job_id: str, path: str):
    f = safe_join(output_dir(job_id), path)
    if not f.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(f, filename=f"{f.parent.name}-{f.name}" if f.parent.name.startswith("c") else f.name)


@router.get("/download-all/{job_id}")
def download_all(job_id: str):
    job = load_job(job_id)
    base = output_dir(job_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for f in sorted((base / "clips").rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(base / "clips").as_posix())
        for clip in job.get("clips", []):
            for pid, p in clip["platforms"].items():
                z.writestr(f"{clip['id']}/{pid}-post.txt", p["content"]["text"])
        ex = job.get("extras") or {}
        if ex.get("blog_markdown"):
            z.writestr("blog.md", ex["blog_markdown"])
        if ex.get("x_thread"):
            z.writestr("x-thread.txt", "\n\n".join(ex["x_thread"]))
        if ex.get("linkedin_post"):
            z.writestr("linkedin-post.txt", ex["linkedin_post"])
    buf.seek(0)
    name = (job.get("title") or "repurposed").replace(" ", "-").lower()
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{name}.zip"'})
