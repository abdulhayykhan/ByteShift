# ByteShift

ByteShift is a FastAPI-based file conversion service with a simple web UI.
It supports image, document, audio, and video conversion routes and streams converted files back to the client.

## Stack

- Backend: FastAPI, Starlette, Uvicorn
- Frontend: HTML, CSS, vanilla JavaScript
- Conversion libraries: Pillow, pdf2docx, docx2pdf, python-docx, pydub, ffmpeg-python, pdf2image, pypdfium2
- Runtime system dependencies: `ffmpeg`, `poppler-utils`

## Supported Conversions

- Image routes:
  - PNG/JPG/JPEG/WEBP -> PNG/JPG/JPEG/WEBP
  - Image -> PDF
  - Image -> DOCX
- Document routes:
  - PDF -> DOCX
  - PDF -> PNG/JPG (first page)
  - DOCX -> PDF (Windows hosts with Microsoft Word)
  - DOCX -> PNG/JPG (depends on DOCX -> PDF capability)
- Audio routes:
  - MP3 <-> WAV
  - Audio (MP3/WAV) -> MP4
- Video routes:
  - MP4 <-> AVI
  - Video (MP4/AVI) -> MP3/WAV

## Railway Deployment

Railway uses a read-only filesystem except for `/tmp`.
ByteShift is configured to use environment-safe paths and writable temp storage.

### Deployment Files Included

- `railway.toml` with build/deploy settings
- `nixpacks.toml` with system packages and start command
- `Procfile` fallback start command
- Pinned `requirements.txt`

### Deploy Steps

1. Push this repository to GitHub.
2. Create a new Railway project from the repo.
3. Railway will detect Nixpacks and install Python dependencies.
4. Railway will install system packages declared in `nixpacks.toml`.
5. App starts with:
   - `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`

## Local Run

```bash
python -m pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://127.0.0.1:8000`.

## Environment Variables

- `PORT`: Provided by Railway at runtime
- `HOST`: Optional, defaults to `0.0.0.0`
- `BYTESHIFT_TEMP_DIR`: Optional temp directory override (defaults to `/tmp`)

## Notes

- On Linux environments (including Railway), DOCX -> PDF and DOCX -> image routes are unavailable because `docx2pdf` requires Microsoft Word.
- All conversion temp files are created in a writable temp directory and cleaned up after response.
