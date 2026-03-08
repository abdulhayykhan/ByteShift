import tempfile
import os
from fastapi import UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from PIL import Image
from PIL import features
from io import BytesIO

SUPPORTED_FORMATS = {"PNG", "JPG", "JPEG", "WEBP"}
MEDIA_TYPES = {
    "PNG": "image/png",
    "JPG": "image/jpeg",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp"
}


def cleanup_file(path: str):
    """Remove temporary file after response is sent."""
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


async def convert_image(file: UploadFile, output_format: str, background_tasks: BackgroundTasks) -> FileResponse:
    """
    Convert an uploaded image to the requested format.
    
    Args:
        file: Uploaded image file (PNG, JPG, WEBP)
        output_format: Target format (PNG, JPG, WEBP)
    
    Returns:
        FileResponse with the converted image
    """
    output_format = output_format.upper()
    
    if output_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {output_format}. Supported: {SUPPORTED_FORMATS}")
    
    # Read the uploaded file
    contents = await file.read()
    
    # Open image with Pillow
    image = Image.open(BytesIO(contents))

    # Some Pillow builds are compiled without WEBP support.
    if output_format == "WEBP" and not features.check("webp"):
        raise ValueError(
            "WEBP conversion is not available in this environment. "
            "Install a Pillow build with WEBP support and try again."
        )
    
    # Convert RGBA to RGB if converting to JPG
    if output_format in ("JPG", "JPEG") and image.mode in ("RGBA", "LA", "P"):
        rgb_image = Image.new("RGB", image.size, (255, 255, 255))
        rgb_image.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
        image = rgb_image
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_format.lower()}")
    temp_path = temp_file.name
    temp_file.close()
    
    # Save converted image
    save_format = output_format if output_format != "JPG" else "JPEG"
    try:
        image.save(temp_path, format=save_format)
    except KeyError as e:
        # Pillow raises KeyError when encoder plugins are unavailable.
        cleanup_file(temp_path)
        raise ValueError(
            f"{output_format} conversion is not available in this environment."
        ) from e
    except Exception:
        cleanup_file(temp_path)
        raise
    
    # Get original filename without extension
    original_name = os.path.splitext(file.filename)[0] if file.filename else "image"
    output_filename = f"{original_name}.{output_format.lower()}"
    
    # Schedule cleanup of output file after response is sent
    background_tasks.add_task(cleanup_file, temp_path)
    
    return FileResponse(
        path=temp_path,
        media_type=MEDIA_TYPES[output_format],
        filename=output_filename,
        headers={"Content-Disposition": f"attachment; filename={output_filename}"}
    )


async def image_to_pdf(file: UploadFile, background_tasks: BackgroundTasks) -> FileResponse:
    """
    Convert an uploaded image to PDF format.

    Args:
        file: Uploaded image file (PNG, JPG, WEBP)

    Returns:
        FileResponse with the image as a PDF
    """
    # Read the uploaded file
    contents = await file.read()

    # Open image with Pillow
    image = Image.open(BytesIO(contents))

    # Convert to RGB (required for PDF)
    if image.mode in ("RGBA", "LA", "P"):
        rgb_image = Image.new("RGB", image.size, (255, 255, 255))
        rgb_image.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
        image = rgb_image
    elif image.mode != "RGB":
        image = image.convert("RGB")

    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_path = temp_file.name
    temp_file.close()

    try:
        # Save image as PDF
        image.save(temp_path, format="PDF")
    except Exception as e:
        cleanup_file(temp_path)
        raise ValueError(f"Failed to convert image to PDF: {str(e)}") from e

    # Get original filename without extension
    original_name = os.path.splitext(file.filename)[0] if file.filename else "image"
    output_filename = f"{original_name}.pdf"

    # Schedule cleanup
    background_tasks.add_task(cleanup_file, temp_path)

    return FileResponse(
        path=temp_path,
        media_type="application/pdf",
        filename=output_filename,
        headers={"Content-Disposition": f"attachment; filename={output_filename}"}
    )
