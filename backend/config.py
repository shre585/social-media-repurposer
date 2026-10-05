"""Central configuration. Everything is driven by environment variables (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "backend" / ".env")


class Settings:
    APP_NAME = "Social Media Repurposer"

    # Storage (local disk by default; mount a volume / swap for blob storage later)
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads")).resolve()
    OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "outputs")).resolve()
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "1024"))

    CORS_ORIGINS = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost:8080").split(",")
        if o.strip()
    ]

    # LLM (leave LLM_PROVIDER empty to auto-detect from whichever key is set)
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # Speech-to-text (faster-whisper, runs locally)
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
    WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
    WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")

    FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
    FFPROBE_BIN = os.getenv("FFPROBE_BIN", "ffprobe")
    MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "1"))

    def llm_provider(self) -> str:
        """Return the provider to use: anthropic | openai | gemini | mock."""
        keys = {
            "anthropic": self.ANTHROPIC_API_KEY,
            "openai": self.OPENAI_API_KEY,
            "gemini": self.GEMINI_API_KEY,
        }
        if self.LLM_PROVIDER == "mock":
            return "mock"
        if self.LLM_PROVIDER in keys and keys[self.LLM_PROVIDER]:
            return self.LLM_PROVIDER
        for name, key in keys.items():
            if key:
                return name
        return "mock"  # no key -> built-in keyword heuristics, app still works


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
