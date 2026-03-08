import os
import tempfile
import zipfile

from docx2pdf import convert as docx_to_pdf_convert
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


def convert_docx_to_pdf_with_retry(input_path: str, output_path: str) -> None:
    """Convert DOCX to PDF with one normalization retry for compatibility issues."""
    if os.name != "nt":
        raise ValueError(
            "DOCX to PDF conversion requires Microsoft Word and is only supported on Windows hosts. "
            "This conversion route is unavailable in this deployment environment."
        )

    original_error = None
    try:
        docx_to_pdf_convert(input_path, output_path)
        return
    except Exception as first_error:
        original_error = first_error

    # Some generated DOCX files fail in docx2pdf. Re-save once via python-docx.
    normalized_fd, normalized_path = tempfile.mkstemp(suffix=".docx")
    os.close(normalized_fd)
    try:
        from docx import Document

        doc = Document(input_path)
        doc.save(normalized_path)
        try:
            docx_to_pdf_convert(normalized_path, output_path)
            return
        except Exception as normalized_error:
            # Final fallback: drive Word directly with OpenAndRepair to auto-recover files.
            try:
                from win32com.client import DispatchEx

                wd_format_pdf = 17
                word = DispatchEx("Word.Application")
                word.Visible = False
                doc = None
                try:
                    doc = word.Documents.Open(
                        normalized_path,
                        ConfirmConversions=False,
                        ReadOnly=True,
                        AddToRecentFiles=False,
                        OpenAndRepair=True,
                    )
                    doc.SaveAs(output_path, FileFormat=wd_format_pdf)
                    return
                finally:
                    if doc is not None:
                        doc.Close(False)
                    word.Quit()
            except Exception:
                message = str(normalized_error).lower()
                if "corrupted" in message or "microsoft word" in message or "-214" in message:
                    raise ValueError(
                        "DOCX to PDF conversion failed after automatic repair attempts. "
                        "Please open the file in Microsoft Word, save it as a new .docx, then try again."
                    ) from normalized_error
                if original_error is not None:
                    raise ValueError(f"Failed to convert DOCX to PDF: {str(original_error)}") from original_error
                raise ValueError(f"Failed to convert DOCX to PDF: {str(normalized_error)}") from normalized_error
    except Exception as normalize_error:
        message = str(normalize_error).lower()
        if "corrupted" in message or "microsoft word" in message or "-214" in message:
            raise ValueError(
                "Microsoft Word could not open this DOCX for PDF conversion. "
                "The file may be corrupted or incompatible. Open it in Word and save it as a new .docx, then try again."
            ) from normalize_error
        if original_error is not None:
            raise ValueError(f"Failed to convert DOCX to PDF: {str(original_error)}") from original_error
        raise ValueError(f"Failed to convert DOCX to PDF: {str(normalize_error)}") from normalize_error
    finally:
        cleanup_file(normalized_path)


def raise_docx_com_error_as_value_error(error: Exception, context: str) -> None:
    """Convert raw Word COM errors to user-facing messages."""
    message = str(error).lower()
    if "microsoft word" in message or "-214" in message or "corrupted" in message:
        raise ValueError(
            "Microsoft Word could not convert this DOCX even after automatic repair attempts. "
            "The file may be corrupted or incompatible. Open it in Word and save it as a new .docx file, then try again."
        ) from error
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
            cv.convert(output_path)
            cv.close()
        elif conversion_key == "docx->pdf":
            convert_docx_to_pdf_with_retry(input_path, output_path)

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
        convert_docx_to_pdf_with_retry(docx_path, pdf_path)

        with open(pdf_path, "rb") as pdf_file:
            pdf_contents = pdf_file.read()

        image = render_first_pdf_page(pdf_contents)
    except ValueError as e:
        # Preserve domain-specific, user-friendly validation errors.
        raise_docx_com_error_as_value_error(e, "Failed to convert DOCX to image")
    except Exception as e:
        raise_docx_com_error_as_value_error(e, "Failed to convert DOCX to image")
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
