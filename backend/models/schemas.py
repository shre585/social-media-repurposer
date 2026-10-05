from typing import Optional

from pydantic import BaseModel, Field


class UrlUpload(BaseModel):
    url: str


class ProcessRequest(BaseModel):
    job_id: str
    platforms: list[str] = Field(default_factory=lambda: ["instagram", "youtube"])
    tone: str = "educational"          # educational | genz | professional | funny
    language: str = "english"          # english | hinglish | hindi
    max_clips: int = Field(6, ge=1, le=15)
    min_clip_seconds: int = Field(20, ge=5, le=120)
    max_clip_seconds: int = Field(60, ge=10, le=180)
    reframe: str = "blur"              # blur (fit + blurred bg) | crop (fill frame)


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[list[str]] = None
