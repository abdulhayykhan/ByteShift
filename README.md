# ByteShift
### Convert Anything, Instantly

ByteShift is a fast, single-page file converter built with FastAPI. Upload any supported file, pick your output format, and download the result — no sign-up, no limits, no ads.

Live at: **[byteshift.up.railway.app](https://byteshift.up.railway.app)**

---

## Features

- **Single unified converter** — one clean two-panel UI, no separate forms per category
- **Auto format detection** — upload a file and the right output options appear automatically
- **Cross-sectional conversions** — convert across categories (e.g. image → PDF, video → audio)
- **Dark / Light mode** — toggle with a single click, pure CSS
- **No JS frameworks** — frontend is plain HTML + CSS with minimal JS only where necessary
- **Production-ready** — deployed on Railway with LibreOffice, ffmpeg, and Poppler pre-installed

---

## Supported Conversions

| Input | Output Options |
|---|---|
| PNG, JPG, WEBP | ↔ each other · PDF |
| PDF | DOCX · PNG · JPG |
| DOCX | PDF · PNG · JPG |
| MP3, WAV | ↔ each other · MP4 |
| MP4, AVI | ↔ each other · MP3 · WAV |

---

## Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com) + [Uvicorn](https://www.uvicorn.org) + [Gunicorn](https://gunicorn.org) (production)
- [Pillow](https://pillow.readthedocs.io) — image conversion + image→PDF
- [pdf2docx](https://pdf2docx.readthedocs.io) — PDF→DOCX
- [pdf2image](https://github.com/Belval/pdf2image) + [pypdfium2](https://pypdfium2.readthedocs.io) — PDF→image (dual backend)
- [LibreOffice headless](https://www.libreoffice.org) — DOCX→PDF on Linux
- [pydub](https://github.com/jiaaro/pydub) — audio conversion
- [ffmpeg-python](https://github.com/kkroening/ffmpeg-python) — video conversion + audio extraction

**Frontend**
- HTML5 + CSS3 (no frameworks)
- Vanilla JavaScript (fetch-based form submission, loading overlay, error toasts)

**System Dependencies**
- `ffmpeg` — audio/video processing
- `poppler-utils` — PDF rendering
- `libreoffice` — DOCX→PDF on Linux

---

## Local Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install system dependencies (Windows)
# ffmpeg: https://ffmpeg.org/download.html
# poppler: https://github.com/oschwartz10612/poppler-windows
# libreoffice: https://www.libreoffice.org/download

# Run development server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://127.0.0.1:8000`

---

## Railway Deployment

ByteShift is pre-configured for Railway. All required files are included in the repo.

### Deployment Files

| File | Purpose |
|---|---|
| `nixpacks.toml` | System packages (ffmpeg, poppler-utils, libreoffice) + start command |
| `railway.toml` | Builder, deploy command, healthcheck path, restart policy |
| `Procfile` | Fallback start command |
| `requirements.txt` | Pinned Python dependencies |

### Deploy Steps

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
3. Select the ByteShift repo
4. Railway auto-detects Nixpacks and installs all dependencies
5. App starts automatically with:
```
gunicorn -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:${PORT:-8000} main:app
```

### Health Check

```
GET /healthz → { "status": "ok" }
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` | Provided automatically by Railway |
| `HOST` | `0.0.0.0` | Server bind address |
| `BYTESHIFT_TEMP_DIR` | `/tmp` | Writable temp directory for conversions |
| `SECRET_KEY` | — | Set this in Railway Variables |
| `DEBUG` | `False` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Architecture Notes

- **Temp file safety** — all conversions write to `/tmp` (writable on Railway's read-only filesystem) and clean up automatically after the response is sent via `BackgroundTasks`
- **LibreOffice isolation** — each DOCX→PDF conversion runs with its own temporary user profile under `/tmp` to support concurrent requests safely
- **PDF rendering fallback** — PDF→image tries `pdf2image` (Poppler) first, then falls back to `pypdfium2` automatically if Poppler is unavailable
- **Progress tracking** — a thread-safe `ProgressTracker` monitors each conversion job with stale job cleanup after 15 minutes
- **Error handling** — all conversion errors return structured JSON with user-friendly messages; no raw tracebacks exposed to the client

---

## Project Structure

```
byteshift/
├── main.py                  # FastAPI app, all routes
├── config.py                # Settings, environment config, runtime setup
├── converters/
│   ├── image.py             # Image ↔ image, image → PDF
│   ├── document.py          # PDF ↔ DOCX, PDF/DOCX → image
│   ├── audio.py             # MP3 ↔ WAV
│   ├── video.py             # MP4 ↔ AVI, video → audio, audio → video
│   └── progress.py          # Thread-safe job progress tracker
├── static/
│   └── style.css            # Dark/light theme, animations, UI
├── templates/
│   └── index.html           # Single-page UI with two-panel converter
├── nixpacks.toml            # Railway system packages
├── railway.toml             # Railway deploy config
├── Procfile                 # Fallback start command
└── requirements.txt         # Pinned Python dependencies
```

---

## 📄 License

This project is open-source and available for educational and commercial use under the MIT License.

---

**Made with ❤️ by [Abdul Hayy Khan](https://www.linkedin.com/in/abdulhayykhan/)**