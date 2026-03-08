import os
import shutil
import subprocess
import tempfile
import zipfile

from fastapi import BackgroundTasks, UploadFile
from fastapi.responses import FileResponse
from pdf2docx import Converter
from PIL import Image

SUPPORTED_CONVERSIONS = {
    "pdf->docx": ("pdf", "docx"),
    "docx->pdf": ("docx", "pdf"),
}

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def cleanup_file(path: str):
    """Remove temporary file after response is sent."""
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


def validate_docx_bytes(contents: bytes) -> None:
    """Validate that bytes represent a minimally valid DOCX package."""
    if not contents:
        raise ValueError("The uploaded DOCX file is empty.")

    try:
        from io import BytesIO

        with zipfile.ZipFile(BytesIO(contents), "r") as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile as e:
        raise ValueError("The uploaded DOCX is not a valid Word file (invalid ZIP structure).") from e
    except Exception as e:
        raise ValueError(f"Unable to read DOCX file: {str(e)}") from e

    required_entries = {"[Content_Types].xml", "word/document.xml"}
    missing = required_entries - names
    if missing:
        raise ValueError(
            "The uploaded DOCX appears corrupted or incomplete. "
            "Please open it in Word and Save As a new .docx file, then retry."
        )


def convert_docx_to_pdf_libreoffice(input_path: str, output_dir: str) -> str:
    """
    Uses LibreOffice in headless mode to convert DOCX to PDF.
    Returns the path to the generated PDF file.
    """
    libreoffice_cmd = shutil.which("libreoffice") or shutil.which("soffice")
    if libreoffice_cmd is None:
        raise RuntimeError(
            "LibreOffice executable not found on PATH. Install LibreOffice (or ensure soffice is available)."
        )

    result = subprocess.run(
        [
            libreoffice_cmd,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            output_dir,
            input_path,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "unknown LibreOffice error").strip()
        raise RuntimeError(f"LibreOffice conversion failed: {details}")

    # LibreOffice outputs filename.pdf in output_dir
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    pdf_path = os.path.join(output_dir, base_name + ".pdf")
    if not os.path.exists(pdf_path):
        raise RuntimeError("LibreOffice did not produce output file.")
    return pdf_path


def raise_docx_conversion_error(error: Exception, context: str) -> None:
    """Convert DOCX conversion errors into user-facing messages."""
    raise ValueError(f"{context}: {str(error)}") from error


def render_first_pdf_page(contents: bytes) -> Image.Image:
    """Render the first PDF page to a PIL image with Poppler-free fallback."""
    try:
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(contents)
        if images:
            return images[0]
    except Exception as e:
        message = str(e).lower()
        poppler_related = "poppler" in message or "unable to get page count" in message
        if not poppler_related:
            raise ValueError(f"Failed to render PDF page: {str(e)}") from e

    # Poppler is unavailable: fallback to pypdfium2 rendering.
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(contents)
        if len(pdf) == 0:
            raise ValueError("PDF appears to be empty")
        page = pdf[0]
        bitmap = page.render(scale=2.0)
        pil_image = bitmap.to_pil()
        page.close()
        pdf.close()
        return pil_image
    except ImportError as e:
        raise ValueError(
            "PDF rendering backend unavailable. Install pypdfium2 to enable PDF to image conversion without Poppler."
        ) from e
    except Exception as e:
        raise ValueError(f"Failed to render PDF page with fallback backend: {str(e)}") from e


async def convert_document(
    file: UploadFile, output_format: str, background_tasks: BackgroundTasks
) -> FileResponse:
    """Convert a document between PDF and DOCX formats."""
    output_format = output_format.lower()

    filename_lower = file.filename.lower() if file.filename else ""
    if filename_lower.endswith(".pdf"):
        input_format = "pdf"
    elif filename_lower.endswith(".docx"):
        input_format = "docx"
    else:
        raise ValueError("Input file must be PDF or DOCX")

    conversion_key = f"{input_format}->{output_format}"
    if conversion_key not in SUPPORTED_CONVERSIONS:
        raise ValueError(
            f"Conversion {conversion_key} not supported. "
            "Supported: PDF->DOCX, DOCX->PDF"
        )

    contents = await file.read()

    if input_format == "docx":
        validate_docx_bytes(contents)

    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=f".{input_format}")
    temp_input.write(contents)
    temp_input.close()
    input_path = temp_input.name

    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_format}")
    output_path = temp_output.name
    temp_output.close()

    try:
        if conversion_key == "pdf->docx":
            cv = Converter(input_path)
            try:
                cv.convert(output_path)
            finally:
                cv.close()
        elif conversion_key == "docx->pdf":
            generated_pdf = convert_docx_to_pdf_libreoffice(input_path, os.path.dirname(output_path))
            if generated_pdf != output_path:
                if os.path.exists(output_path):
                    cleanup_file(output_path)
                os.replace(generated_pdf, output_path)

        original_name = os.path.splitext(file.filename)[0] if file.filename else "document"
        output_filename = f"{original_name}.{output_format}"

        background_tasks.add_task(cleanup_file, output_path)

        return FileResponse(
            path=output_path,
            media_type=MEDIA_TYPES[output_format],
            filename=output_filename,
            headers={"Content-Disposition": f"attachment; filename={output_filename}"},
        )
    finally:
        cleanup_file(input_path)


async def pdf_to_image(
    file: UploadFile, output_format: str, background_tasks: BackgroundTasks
) -> FileResponse:
    """Convert the first page of a PDF to PNG or JPG."""
    output_format = output_format.lower()
    if output_format not in ("png", "jpg"):
        raise ValueError(f"Unsupported output format: {output_format}. Supported: png, jpg")

    contents = await file.read()

    try:
        image = render_first_pdf_page(contents)
    except Exception as e:
        raise ValueError(f"Failed to convert PDF to image: {str(e)}") from e

    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_format}")
    output_path = temp_output.name
    temp_output.close()

    try:
        save_format = "JPEG" if output_format == "jpg" else "PNG"
        image.save(output_path, format=save_format)
    except Exception as e:
        cleanup_file(output_path)
        raise ValueError(f"Failed to save image: {str(e)}") from e

    original_name = os.path.splitext(file.filename)[0] if file.filename else "document"
    output_filename = f"{original_name}.{output_format}"

    background_tasks.add_task(cleanup_file, output_path)

    media_type = "image/jpeg" if output_format == "jpg" else "image/png"
    return FileResponse(
        path=output_path,
        media_type=media_type,
        filename=output_filename,
        headers={"Content-Disposition": f"attachment; filename={output_filename}"},
    )


async def docx_to_image(
    file: UploadFile, output_format: str, background_tasks: BackgroundTasks
) -> FileResponse:
    """Convert DOCX to PNG or JPG by first converting it to PDF."""
    output_format = output_format.lower()
    if output_format not in ("png", "jpg"):
        raise ValueError(f"Unsupported output format: {output_format}. Supported: png, jpg")

    contents = await file.read()
    validate_docx_bytes(contents)

    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    temp_input.write(contents)
    temp_input.close()
    docx_path = temp_input.name

    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_path = temp_pdf.name
    temp_pdf.close()

    try:
        generated_pdf = convert_docx_to_pdf_libreoffice(docx_path, os.path.dirname(pdf_path))
        if generated_pdf != pdf_path:
            if os.path.exists(pdf_path):
                cleanup_file(pdf_path)
            pdf_path = generated_pdf

        with open(pdf_path, "rb") as pdf_file:
            pdf_contents = pdf_file.read()

        image = render_first_pdf_page(pdf_contents)
    except ValueError as e:
        # Preserve domain-specific, user-friendly validation errors.
        raise_docx_conversion_error(e, "Failed to convert DOCX to image")
    except Exception as e:
        raise_docx_conversion_error(e, "Failed to convert DOCX to image")
    finally:
        cleanup_file(docx_path)
        cleanup_file(pdf_path)

    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_format}")
    output_path = temp_output.name
    temp_output.close()

    try:
        save_format = "JPEG" if output_format == "jpg" else "PNG"
        image.save(output_path, format=save_format)
    except Exception as e:
        cleanup_file(output_path)
        raise ValueError(f"Failed to save image: {str(e)}") from e

    original_name = os.path.splitext(file.filename)[0] if file.filename else "document"
    output_filename = f"{original_name}.{output_format}"

    background_tasks.add_task(cleanup_file, output_path)

    media_type = "image/jpeg" if output_format == "jpg" else "image/png"
    return FileResponse(
        path=output_path,
        media_type=media_type,
        filename=output_filename,
        headers={"Content-Disposition": f"attachment; filename={output_filename}"},
    )
