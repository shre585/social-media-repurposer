from fastapi import APIRouter, BackgroundTasks, HTTPException

from models.schemas import ProcessRequest
from services.llm_analysis import llm_enabled
from services.pipeline import run_pipeline
from services.platform_formatter import PLATFORMS
from utils.file_utils import load_job, update_job
from config import settings

router = APIRouter(tags=["process"])


@router.get("/platforms")
def platforms():
    return {"platforms": list(PLATFORMS.values()),
            "ai_enabled": llm_enabled(), "provider": settings.llm_provider()}


@router.post("/process")
def process(req: ProcessRequest, background: BackgroundTasks):
    job = load_job(req.job_id)
    if job["status"] == "processing":
        raise HTTPException(409, "This project is already being processed.")
    if req.max_clip_seconds < req.min_clip_seconds:
        raise HTTPException(400, "Max clip length must be longer than min clip length.")
    update_job(req.job_id, status="queued", progress=1, stage=None, message="Waiting for a free worker…", error=None)
    background.add_task(run_pipeline, req.job_id, req.model_dump())
    return {"job_id": req.job_id, "status": "queued"}


@router.get("/status/{job_id}")
def status(job_id: str):
    j = load_job(job_id)
    return {k: j.get(k) for k in ("id", "status", "stage", "progress", "message", "error", "steps", "kind", "title")}
