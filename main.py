from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.requests import Request
from converters.image import convert_image
from converters.document import convert_document
from converters.progress import progress_tracker
from config import settings, configure_runtime

configure_runtime()

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))


async def execute_with_progress(job_id: str, conversion_coro):
    """Run conversion and publish route-level progress states for the UI."""
    if job_id:
        progress_tracker.start(job_id)
        progress_tracker.update(job_id, 15, "Validating input")
        progress_tracker.update(job_id, 55, "Converting file")
    try:
        response = await conversion_coro
        if job_id:
            progress_tracker.update(job_id, 90, "Preparing download")
            progress_tracker.complete(job_id, "Conversion complete")
        return response
    except Exception as e:
        if job_id:
            progress_tracker.fail(job_id, str(e))
        raise

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/convert/image")
async def convert_image_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    output_format: str = Form(...),
    job_id: str = Form(default="")
):
    """
    Convert an uploaded image to the requested format.
    
    Args:
        file: Image file to convert
        output_format: Target format (PNG, JPG, WEBP)
    
    Returns:
        Converted image as a downloadable file
    """
    try:
        return await execute_with_progress(job_id, convert_image(file, output_format, background_tasks))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image conversion failed: {str(e)}")

@app.post("/convert/document")
async def convert_document_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    output_format: str = Form(...),
    job_id: str = Form(default="")
):
    """
    Convert an uploaded document to the requested format.
    
    Args:
        file: Document file to convert (PDF or DOCX)
        output_format: Target format (pdf or docx)
    
    Returns:
        Converted document as a downloadable file
    """
    try:
        return await execute_with_progress(job_id, convert_document(file, output_format, background_tasks))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document conversion failed: {str(e)}")

@app.post("/convert/audio")
async def convert_audio_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    output_format: str = Form(...),
    job_id: str = Form(default="")
):
    """
    Convert an uploaded audio file to the requested format.
    
    Args:
        file: Audio file to convert (MP3 or WAV)
        output_format: Target format (mp3 or wav)
    
    Returns:
        Converted audio as a downloadable file
    """
    try:
        # Lazy import to avoid startup issues with pydub on Python 3.13+
        from converters.audio import convert_audio
        return await execute_with_progress(job_id, convert_audio(file, output_format, background_tasks))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio conversion failed: {str(e)}")

@app.post("/convert/video")
async def convert_video_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    output_format: str = Form(...),
    job_id: str = Form(default="")
):
    """
    Convert an uploaded video file to the requested format.
    
    Args:
        file: Video file to convert (MP4 or AVI)
        output_format: Target format (mp4 or avi)
    
    Returns:
        Converted video as a downloadable file
    """
    try:
        from converters.video import convert_video
        return await execute_with_progress(job_id, convert_video(file, output_format, background_tasks))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video conversion failed: {str(e)}")

@app.post("/convert/image-to-pdf")
async def image_to_pdf_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_id: str = Form(default="")
):
    """Convert an image to PDF."""
    try:
        from converters.image import image_to_pdf
        return await execute_with_progress(job_id, image_to_pdf(file, background_tasks))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image to PDF conversion failed: {str(e)}")

@app.post("/convert/image-to-docx")
async def image_to_docx_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_id: str = Form(default="")
):
    """Convert an image to DOCX."""
    try:
        from converters.image import image_to_docx
        return await execute_with_progress(job_id, image_to_docx(file, background_tasks))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image to DOCX conversion failed: {str(e)}")

@app.post("/convert/pdf-to-image")
async def pdf_to_image_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    output_format: str = Form(...),
    job_id: str = Form(default="")
):
    """Convert PDF first page to image (PNG or JPG)."""
    try:
        from converters.document import pdf_to_image
        return await execute_with_progress(job_id, pdf_to_image(file, output_format, background_tasks))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF to image conversion failed: {str(e)}")

@app.post("/convert/docx-to-image")
async def docx_to_image_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    output_format: str = Form(...),
    job_id: str = Form(default="")
):
    """Convert DOCX to image (PNG or JPG)."""
    try:
        from converters.document import docx_to_image
        return await execute_with_progress(job_id, docx_to_image(file, output_format, background_tasks))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DOCX to image conversion failed: {str(e)}")

@app.post("/convert/video-to-audio")
async def video_to_audio_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    output_format: str = Form(...),
    job_id: str = Form(default="")
):
    """Extract audio from video (MP3 or WAV)."""
    try:
        from converters.video import video_to_audio
        return await execute_with_progress(job_id, video_to_audio(file, output_format, background_tasks))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video to audio conversion failed: {str(e)}")

@app.post("/convert/audio-to-video")
async def audio_to_video_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_id: str = Form(default="")
):
    """Convert audio to video (black background)."""
    try:
        from converters.video import audio_to_video
        return await execute_with_progress(job_id, audio_to_video(file, background_tasks))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio to video conversion failed: {str(e)}")


@app.get("/progress/{job_id}")
async def get_progress(job_id: str):
    job = progress_tracker.get(job_id)
    if not job:
        return {"status": "not_found", "progress": 0, "stage": "Unknown", "error": None}
    return job

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
