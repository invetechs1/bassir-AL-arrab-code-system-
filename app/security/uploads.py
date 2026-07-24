"""Secure upload validation: size, extension, filename hygiene, magic bytes.

Files are never stored under their original names — a UUID storage name
is generated and the original name is kept as metadata only, so path
traversal via filename cannot reach the filesystem.
"""

import re
import uuid
from pathlib import PurePosixPath, PureWindowsPath

from app.config import settings


class UploadValidationError(Exception):
    def __init__(self, reason_en: str, reason_ar: str):
        super().__init__(reason_en)
        self.reason_en = reason_en
        self.reason_ar = reason_ar


WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

# Magic-byte signatures per extension. `None` entries are text formats
# checked heuristically instead.
MAGIC_SIGNATURES = {
    ".pdf": [b"%PDF-"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".ifc": [b"ISO-10303-21"],
}

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _extension(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def validate_filename(filename: str) -> str:
    """Return the extension if the filename is safe, else raise."""
    if not filename or len(filename) > 255:
        raise UploadValidationError("invalid filename length", "طول اسم الملف غير صالح")
    if _CONTROL_CHARS.search(filename):
        raise UploadValidationError(
            "filename contains control characters", "اسم الملف يحتوي على رموز تحكم محظورة"
        )
    if "/" in filename or "\\" in filename or ".." in filename:
        raise UploadValidationError(
            "filename contains path traversal characters",
            "اسم الملف يحتوي على رموز مسارات محظورة",
        )
    if filename.startswith(".") or filename.rstrip().endswith("."):
        raise UploadValidationError("hidden or malformed filename", "اسم ملف مخفي أو غير صالح")
    if PurePosixPath(filename).name != filename or PureWindowsPath(filename).name != filename:
        raise UploadValidationError("filename is not a plain name", "اسم الملف ليس اسمًا بسيطًا")

    stem = filename.split(".")[0].lower()
    if stem in WINDOWS_RESERVED:
        raise UploadValidationError("reserved filename", "اسم الملف محجوز في أنظمة التشغيل")

    ext = _extension(filename)
    if ext not in settings.allowed_upload_extensions:
        allowed = ", ".join(settings.allowed_upload_extensions)
        raise UploadValidationError(
            f"extension '{ext}' not allowed (allowed: {allowed})",
            f"امتداد الملف '{ext}' غير مسموح",
        )
    return ext


def validate_content(ext: str, content: bytes) -> None:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) == 0:
        raise UploadValidationError("empty file", "الملف فارغ")
    if len(content) > max_bytes:
        raise UploadValidationError(
            f"file exceeds {settings.max_upload_mb} MB limit",
            f"حجم الملف يتجاوز الحد المسموح ({settings.max_upload_mb} م.ب)",
        )

    signatures = MAGIC_SIGNATURES.get(ext)
    if signatures is not None:
        head = content[:64]
        if not any(head.startswith(sig) or sig in head for sig in signatures):
            raise UploadValidationError(
                "file content does not match its extension (magic bytes)",
                "محتوى الملف لا يطابق امتداده (فحص البصمة الثنائية)",
            )
    elif ext in (".dxf", ".json"):
        # Text formats: refuse binary content that could hide executables.
        if b"\x00" in content[:4096]:
            raise UploadValidationError(
                "binary content in a text-format upload",
                "محتوى ثنائي داخل ملف نصي",
            )


def validate_upload(filename: str, content: bytes) -> dict:
    """Full validation pipeline. Returns storage metadata on success."""
    ext = validate_filename(filename)
    validate_content(ext, content)
    return {
        "original_filename": filename,
        "extension": ext,
        "size_bytes": len(content),
        "storage_name": f"{uuid.uuid4().hex}{ext}",
    }


def store_upload(filename: str, content: bytes) -> dict:
    meta = validate_upload(filename, content)
    settings.ensure_dirs()
    target = settings.uploads_dir / meta["storage_name"]
    target.write_bytes(content)
    meta["stored_path"] = str(target)
    return meta
