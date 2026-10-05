# ☕ Social Media Repurposer

Turn **one** video, podcast, PDF or blog into a week of posts. Upload a 1-hour Python lecture and get short clips cut to each platform's size, plus captions, hashtags, carousels, an X thread, a blog post and SEO text.

```
React (Vite) ──POST /api/upload──▶ FastAPI ──▶ FFmpeg (extract audio)
                                              ──▶ faster-whisper (transcript + timestamps)
                                              ──▶ LLM (topics, titles, captions, hashtags, timestamps)
                                              ──▶ Python validates + snaps timestamps  ◀── scene detection
                                              ──▶ FFmpeg cuts & reframes per platform
                                              ──▶ platform_formatter (limits, hashtags, best time)
React ◀──────────── polls /api/status, then GET /api/results ◀──┘
```

**LLM = brain · Python = controller · FFmpeg = editor · React = UI.** The LLM only *suggests* timestamps; the backend snaps them to sentence boundaries, enforces clip length, ranks them, and only then does FFmpeg cut.

## Input modes

| Mode | Input | What you get |
|---|---|---|
| Video | MP4, MOV, MKV, WEBM, YouTube link | Clips per platform (9:16 / 4:5 / 1:1 / 16:9), thumbnails, `.srt` captions, posts |
| Audio | MP3, WAV, M4A | Audio clip + animated waveform video per platform, posts |
| Document | PDF, DOCX | Concepts → posts, carousels, thread, blog |
| Text | TXT, MD | Same as document |

## Features

- Smart clip picking: AI importance + speaking energy + scene-change awareness (slide changes, cuts)
- Cuts never start or stop mid-sentence
- Auto reframing: blurred-background fit **or** crop-to-fill
- Platforms: Instagram Reels, YouTube Shorts, YouTube Video, Facebook, X, Snapchat, LinkedIn
- Per-platform title/caption/hashtag rules + suggested best posting time
- Tone (Educational / Gen-Z / Professional / Funny) and language (English / Hinglish / Hindi)
- Edit any caption in the browser, copy it, download clip / `.srt`, or download everything as a `.zip`
- Carousel slide text, YouTube chapters, X thread, LinkedIn post, blog, SEO title & meta description
- Works **without an API key** (built-in keyword analyser), better with one (Anthropic, OpenAI or Gemini)
- Light "latte" and dark "espresso" themes

## Run locally

Requirements: **Python 3.10+**, **Node 18+**, **FFmpeg** (`ffmpeg -version` must work).

```bash
cp .env.example .env            # add an AI key if you have one (optional)

# 1) backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 2) frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173  (proxies /api and /files to :8000)
```

First transcription downloads the Whisper model (~150 MB for `base`). Use `WHISPER_MODEL=tiny` for a quick test.

## Deploy

### Option A - one server with Docker (simplest)
```bash
cp .env.example .env            # fill in keys
docker compose up --build -d    # app on http://SERVER_IP:8080
```
Put Caddy / Nginx / Cloudflare in front for HTTPS. Use a VM with 2+ vCPU and 4+ GB RAM (video work is CPU heavy). Uploads and outputs live in `./uploads` and `./outputs`.

### Option B - split hosting
- **Backend** → any Docker host (Render, Railway, Fly.io, Azure Container Apps, a VPS). Mount a persistent disk at `/data`. Set `CORS_ORIGINS=https://your-frontend.com`.
- **Frontend** → Vercel / Netlify / Cloudflare Pages. Build command `npm run build`, output `dist`, env var `VITE_API_URL=https://your-backend.com`. Add an SPA fallback rewrite to `/index.html`.

> Free tiers usually can't handle long video processing (CPU, RAM, timeouts, ephemeral disk). Use a paid instance or a VPS for real lectures.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/platforms` | Platform specs + whether AI is enabled |
| POST | `/api/upload` | Multipart file → `{job_id, kind}` |
| POST | `/api/upload-url` | `{url}` → downloads a YouTube link |
| POST | `/api/process` | Start the pipeline `{job_id, platforms, tone, language, max_clips, ...}` |
| GET | `/api/status/{id}` | Stage + progress (poll this) |
| GET | `/api/results/{id}` | Full results |
| PUT | `/api/results/{id}/clips/{clip}/{platform}` | Save edited title/caption/hashtags |
| GET | `/api/download/{id}/{path}` · `/api/download-all/{id}` | Files / zip |
| GET | `/api/jobs` · DELETE `/api/results/{id}` | Dashboard |

Interactive docs: `http://localhost:8000/docs`

## Project layout

```
backend/   main.py, config.py, routes/, services/ (pipeline, transcription, llm_analysis,
           clip_generator, platform_formatter, content_generator, pdf/text processors), models/, utils/
frontend/  src/{components,pages,services}, vite + nginx config
uploads/ outputs/   local storage (git-ignored)
```

## Roadmap ideas

- Azure Blob / S3 storage instead of local disk · PostgreSQL instead of JSON job files · user accounts
- OCR for scanned PDFs · burned-in animated subtitles · face-tracking crop for vertical video
- Direct posting / scheduling via platform APIs · job queue (Celery/RQ) for many users

---

## Save your project (Git + GitHub)

```bash
cd social-media-repurposer
git init
git add .
git commit -m "Repurposer with new UI"
# create an empty repo on github.com, then:
git remote add origin https://github.com/<you>/social-media-repurposer.git
git branch -M main
git push -u origin main
```
`.env` is git-ignored, so your API keys never get uploaded.

## Deploy

**Option A: one server (easiest, everything works).** Needs a VPS with Docker (DigitalOcean, Hetzner, AWS Lightsail, etc.).
```bash
cp .env.example .env        # add an AI key if you have one
docker compose up -d --build
```
The app is then live on port 8080. Put a domain and HTTPS in front with Caddy or Nginx.

**Option B: split hosting.**
1. Backend: Render / Railway / Fly.io using `backend/Dockerfile` (it already installs ffmpeg). Add a persistent disk mounted at `/data`. Set the env vars from `.env.example`, and `CORS_ORIGINS=https://your-frontend-url`.
2. Frontend: Vercel / Netlify. Root directory `frontend`, build command `npm run build`, output `dist`. Set `VITE_API_URL=https://your-backend-url`. Add a rewrite of all paths to `/index.html` so React Router works.

Video processing (Whisper + ffmpeg) needs real CPU, RAM and disk, so free static hosts can only host the frontend.
