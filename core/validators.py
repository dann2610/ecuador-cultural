from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image_file(file):
    """Valida extensión, tamaño y contenido real de la imagen (evita archivos disfrazados)."""
    ext = Path(file.name).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Formato no permitido. Use JPG, PNG o WEBP.")
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file.size and file.size > max_bytes:
        raise ValidationError(f"La imagen supera el tamaño máximo de {settings.MAX_UPLOAD_SIZE_MB} MB.")
    try:
        pos = file.tell() if hasattr(file, "tell") else 0
        img = Image.open(file)
        fmt = img.format
        img.verify()
        if hasattr(file, "seek"):
            file.seek(pos)
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValidationError("El archivo no es una imagen válida.")
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("El contenido de la imagen no corresponde a un formato permitido.")


def validate_document_file(file):
    """Comprobantes de aporte: imagen o PDF."""
    ext = Path(file.name).suffix.lower()
    if ext == ".pdf":
        if file.size and file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise ValidationError(f"El archivo supera {settings.MAX_UPLOAD_SIZE_MB} MB.")
        head = file.read(5)
        file.seek(0)
        if head != b"%PDF-":
            raise ValidationError("El PDF no es válido.")
        return
    validate_image_file(file)
