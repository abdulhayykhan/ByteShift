import tempfile
import os
from fastapi import UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from pydub import AudioSegment

SUPPORTED_CONVERSIONS = {
    "mp3->wav": ("mp3", "wav"),
    "wav->mp3": ("wav", "mp3")
}

MEDIA_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav"
}


def cleanup_file(path: str):
    """Remove temporary file after response is sent."""
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


async def convert_audio(file: UploadFile, output_format: str, background_tasks: BackgroundTasks) -> FileResponse:
    """
    Convert an audio file between MP3 and WAV formats.
    
    Args:
        file: Uploaded audio file (MP3 or WAV)
        output_format: Target format (mp3 or wav)
    
    Returns:
        FileResponse with the converted audio file
    """
    output_format = output_format.lower()
    
    # Determine input format from filename
    filename_lower = file.filename.lower() if file.filename else ""
    if filename_lower.endswith(".mp3"):
        input_format = "mp3"
    elif filename_lower.endswith(".wav"):
        input_format = "wav"
    else:
        raise ValueError("Input file must be MP3 or WAV")
    
    # Validate conversion
    conversion_key = f"{input_format}->{output_format}"
    if conversion_key not in SUPPORTED_CONVERSIONS:
        raise ValueError(
            f"Conversion {conversion_key} not supported. "
            f"Supported: MP3->WAV, WAV->MP3"
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
        # Load audio file
        audio = AudioSegment.from_file(input_path, format=input_format)
        
        # Export to output format
        audio.export(output_path, format=output_format)
        
        # Get original filename without extension
        original_name = os.path.splitext(file.filename)[0] if file.filename else "audio"
        output_filename = f"{original_name}.{output_format}"
        
        # Schedule cleanup of output file after response is sent
        background_tasks.add_task(cleanup_file, output_path)
        
        return FileResponse(
            path=output_path,
            media_type=MEDIA_TYPES[output_format],
            filename=output_filename,
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )
    
    finally:
        # Clean up input temp file immediately
        try:
            os.unlink(input_path)
        except Exception:
            pass
