"""Audio-track extraction (from video) + speech-to-text with timestamps (faster-whisper)."""
from pathlib import Path

from config import settings
from utils.file_utils import run_cmd

_model = None


def extract_audio(src: Path, dst: Path) -> None:
    """A video's sound track -> 16 kHz mono WAV (what Whisper likes best)."""
    run_cmd([settings.FFMPEG_BIN, "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
             "-c:a", "pcm_s16le", str(dst)])


def _get_model():
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError("faster-whisper is not installed. Run: pip install faster-whisper") from e
        _model = WhisperModel(settings.WHISPER_MODEL, device=settings.WHISPER_DEVICE,
                              compute_type=settings.WHISPER_COMPUTE)
    return _model


def transcribe(audio_path: Path, language: str | None = None) -> tuple[list[dict], str]:
    """Returns ([{start, end, text}, ...], detected_language). Timestamps are in seconds."""
    model = _get_model()
    segments, info = model.transcribe(str(audio_path), language=language, vad_filter=True, beam_size=5)
    out = []
    for s in segments:
        text = s.text.strip()
        if text:
            out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": text})
    return out, info.language
