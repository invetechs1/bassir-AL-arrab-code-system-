"""Basic file inspection shared by /assess/file and /assess/vision.

Foundation level: identifies the real file type, extracts cheap
metadata (PDF page count, PNG dimensions, IFC schema), and reports what
the full pipeline will do. No fake AI output is fabricated.
"""

import re
import struct


def detect_type(content: bytes) -> str:
    if content.startswith(b"%PDF-"):
        return "pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if b"ISO-10303-21" in content[:256]:
        return "ifc"
    head = content[:4096]
    if b"SECTION" in head and b"HEADER" in head:
        return "dxf"
    return "unknown"


def analyze(filename: str, content: bytes) -> dict:
    ftype = detect_type(content)
    meta = {"detected_type": ftype, "size_bytes": len(content), "filename": filename}

    if ftype == "pdf":
        meta["page_count_estimate"] = len(re.findall(rb"/Type\s*/Page[^s]", content))
    elif ftype == "png" and len(content) >= 24:
        width, height = struct.unpack(">II", content[16:24])
        meta["width_px"], meta["height_px"] = width, height
    elif ftype == "ifc":
        schema = re.search(rb"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", content[:4096])
        if schema:
            meta["ifc_schema"] = schema.group(1).decode("ascii", "replace")

    return meta
