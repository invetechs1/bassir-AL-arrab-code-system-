"""Drawing/vision analysis foundation.

The MVP does NOT run a computer-vision model. This module inspects the
uploaded drawing, validates it, and returns an honest foundation
response describing extracted metadata and the roadmap capabilities.
"""

from app.engine.file_analysis import analyze
from app.legal import disclaimer

ROADMAP_CAPABILITIES = [
    "sheet and title-block detection",
    "scale and dimension extraction",
    "setback measurement from site plans",
    "room labeling and area take-off",
]


def analyze_drawing(filename: str, content: bytes) -> dict:
    meta = analyze(filename, content)
    supported = meta["detected_type"] in ("pdf", "png", "jpeg", "dxf")
    return {
        "kind": "vision_foundation",
        "status": "metadata_extracted" if supported else "unsupported_format",
        "file": meta,
        "automated_findings": [],
        "roadmap_capabilities": ROADMAP_CAPABILITIES,
        "note_ar": "تحليل الرسومات بالرؤية الحاسوبية قيد التطوير — تم استخراج البيانات الوصفية فقط في هذه المرحلة.",
        "note_en": "Computer-vision drawing analysis is in development — only file metadata was extracted at this stage.",
        "disclaimer": disclaimer(),
    }
