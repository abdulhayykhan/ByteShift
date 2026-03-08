import tempfile
import os
from fastapi import UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
import ffmpeg

SUPPORTED_CONVERSIONS = {
    "mp4->avi": ("mp4", "avi"),
    "avi->mp4": ("avi", "mp4")
}

MEDIA_TYPES = {
    "mp4": "video/mp4",
    "avi": "video/x-msvideo"
}


def cleanup_file(path: str):
    """Remove temporary file after response is sent."""
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


def format_ffmpeg_error(error: Exception, action: str) -> ValueError:
    """Convert ffmpeg/python exceptions into user-friendly errors with stderr details."""
    if isinstance(error, FileNotFoundError):
        return ValueError(
            f"{action} failed: ffmpeg executable was not found on the system PATH. "
            "Install FFmpeg and ensure ffmpeg.exe is available."
        )

    if isinstance(error, ffmpeg.Error):
        stderr = error.stderr.decode("utf-8", errors="replace") if error.stderr else ""
        stdout = error.stdout.decode("utf-8", errors="replace") if error.stdout else ""
        details = (stderr or stdout or str(error)).strip()

        if details:
            # Keep only the most relevant tail lines to avoid huge API payloads.
            tail = "\n".join(details.splitlines()[-8:])
            return ValueError(f"{action} failed: {tail}")

    return ValueError(f"{action} failed: {str(error)}")


async def convert_video(file: UploadFile, output_format: str, background_tasks: BackgroundTasks) -> FileResponse:
    """
    Convert a video file between MP4 and AVI formats.
    
    Args:
        file: Uploaded video file (MP4 or AVI)
        output_format: Target format (mp4 or avi)
    
    Returns:
        FileResponse with the converted video file
    """
    output_format = output_format.lower()
    
    # Determine input format from filename
    filename_lower = file.filename.lower() if file.filename else ""
    if filename_lower.endswith(".mp4"):
        input_format = "mp4"
    elif filename_lower.endswith(".avi"):
        input_format = "avi"
    else:
        raise ValueError("Input file must be MP4 or AVI")
    
    # Validate conversion
    conversion_key = f"{input_format}->{output_format}"
    if conversion_key not in SUPPORTED_CONVERSIONS:
        raise ValueError(
            f"Conversion {conversion_key} not supported. "
            f"Supported: MP4->AVI, AVI->MP4"
        )
    
    # Read the uploaded file
    contents = await file.read()
    
    # Create temporary input file
    temp_input = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=f".{input_format}"
    )
    temp_input.write(contents)
    temp_input.close()
    input_path = temp_input.name
    
    # Create temporary output file
    temp_output = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=f".{output_format}"
    )
    output_path = temp_output.name
    temp_output.close()
    
    try:
        # Convert video using ffmpeg
        (
            ffmpeg
            .input(input_path)
            .output(output_path, **{'c:v': 'libx264', 'c:a': 'aac'} if output_format == 'mp4' else {})
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        # Get original filename without extension
        original_name = os.path.splitext(file.filename)[0] if file.filename else "video"
        output_filename = f"{original_name}.{output_format}"
        
        # Schedule cleanup of output file after response is sent
        background_tasks.add_task(cleanup_file, output_path)
        
        return FileResponse(
            path=output_path,
            media_type=MEDIA_TYPES[output_format],
            filename=output_filename,
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )
    except Exception as e:
        cleanup_file(output_path)
        raise format_ffmpeg_error(e, "Video conversion") from e
    
    finally:
        # Clean up input temp file immediately
        try:
            os.unlink(input_path)
        except Exception:
            pass


async def video_to_audio(file: UploadFile, output_format: str, background_tasks: BackgroundTasks) -> FileResponse:
    """
    Extract audio from a video file and save as MP3 or WAV.

    Args:
        file: Uploaded video file (MP4 or AVI)
        output_format: Target format (mp3 or wav)

    Returns:
        FileResponse with the extracted audio
    """
    output_format = output_format.lower()

    if output_format not in ("mp3", "wav"):
        raise ValueError(f"Unsupported output format: {output_format}. Supported: mp3, wav")

    # Read the uploaded video
    contents = await file.read()

    # Create temporary input video file
    filename_lower = file.filename.lower() if file.filename else ""
    if filename_lower.endswith(".mp4"):
        input_format = "mp4"
    elif filename_lower.endswith(".avi"):
        input_format = "avi"
    else:
        raise ValueError("Input file must be MP4 or AVI")

    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=f".{input_format}")
    temp_input.write(contents)
    temp_input.close()
    input_path = temp_input.name

    # Create temporary output file
    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_format}")
    output_path = temp_output.name
    temp_output.close()

    try:
        # Extract audio using ffmpeg
        (
            ffmpeg
            .input(input_path)
            .audio
            .output(output_path, acodec="libmp3lame" if output_format == "mp3" else "pcm_s16le")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

        # Get original filename
        original_name = os.path.splitext(file.filename)[0] if file.filename else "audio"
        output_filename = f"{original_name}.{output_format}"

        # Schedule cleanup
        background_tasks.add_task(cleanup_file, output_path)

        media_type = "audio/mpeg" if output_format == "mp3" else "audio/wav"
        return FileResponse(
            path=output_path,
            media_type=media_type,
            filename=output_filename,
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )
    except Exception as e:
        cleanup_file(output_path)
        raise format_ffmpeg_error(e, "Video to audio conversion") from e
    finally:
        cleanup_file(input_path)


async def audio_to_video(file: UploadFile, background_tasks: BackgroundTasks) -> FileResponse:
    """
    Convert audio to video by combining with a black video background.

    Args:
        file: Uploaded audio file (MP3 or WAV)

    Returns:
        FileResponse with the video (MP4)
    """
    # Read the uploaded audio
    contents = await file.read()

    # Create temporary input audio file
    filename_lower = file.filename.lower() if file.filename else ""
    if filename_lower.endswith(".mp3"):
        input_format = "mp3"
    elif filename_lower.endswith(".wav"):
        input_format = "wav"
    else:
        raise ValueError("Input file must be MP3 or WAV")

    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=f".{input_format}")
    temp_input.write(contents)
    temp_input.close()
    input_path = temp_input.name

    # Create temporary output file
    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    output_path = temp_output.name
    temp_output.close()

    try:
        # Create video with black background and audio
        # First get the duration of audio
        probe = ffmpeg.probe(input_path)
        duration = float(probe["format"]["duration"])

        # Create video from audio with black background
        video_stream = ffmpeg.input("color=black:s=1280x720", f="lavfi", t=duration)
        audio_stream = ffmpeg.input(input_path)
        (
            ffmpeg
            .output(
                video_stream,
                audio_stream,
                output_path,
                shortest=None,
                **{"c:v": "libx264", "c:a": "aac", "pix_fmt": "yuv420p"},
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

        # Get original filename
        original_name = os.path.splitext(file.filename)[0] if file.filename else "audio"
        output_filename = f"{original_name}.mp4"

        # Schedule cleanup
        background_tasks.add_task(cleanup_file, output_path)

        return FileResponse(
            path=output_path,
            media_type="video/mp4",
            filename=output_filename,
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )
    except Exception as e:
        cleanup_file(output_path)
        raise format_ffmpeg_error(e, "Audio to video conversion") from e
    finally:
        cleanup_file(input_path)
