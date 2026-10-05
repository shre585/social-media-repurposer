"""Social Media Repurposer - FastAPI entrypoint.   Run:  uvicorn main:app --reload --port 8000"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from routes import process, results, upload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title=settings.APP_NAME, version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(upload.router, prefix="/api")
app.include_router(process.router, prefix="/api")
app.include_router(results.router, prefix="/api")

# generated clips / thumbnails are streamed from here (supports HTTP range requests for video seeking)
app.mount("/files", StaticFiles(directory=settings.OUTPUT_DIR), name="files")


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_provider": settings.llm_provider(), "whisper_model": settings.WHISPER_MODEL}
