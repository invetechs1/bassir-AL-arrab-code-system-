"""BIM/IFC review foundation.

Accepts either declared model statistics or an uploaded IFC file (from
which header metadata is parsed). Performs structural sanity checks on
the model container — not a code-compliance ruling.
"""

from app.engine.file_analysis import analyze
from app.legal import disclaimer

SUPPORTED_SCHEMAS = ("IFC2X3", "IFC4", "IFC4X3")


def review(model_info: dict = None, filename: str = None, content: bytes = None) -> dict:
    model_info = dict(model_info or {})
    file_meta = None

    if content is not None:
        file_meta = analyze(filename or "model.ifc", content)
        if file_meta["detected_type"] != "ifc":
            return {
                "kind": "bim_review",
                "status": "invalid_file",
                "checks": [],
                "file": file_meta,
                "note_ar": "الملف المرفوع ليس ملف IFC صالحًا.",
                "note_en": "The uploaded file is not a valid IFC file.",
                "disclaimer": disclaimer(),
            }
        model_info.setdefault("schema", file_meta.get("ifc_schema", ""))

    checks = []

    schema = str(model_info.get("schema", "")).upper()
    schema_ok = any(schema.startswith(s) for s in SUPPORTED_SCHEMAS) if schema else False
    checks.append({
        "check": "ifc_schema_supported",
        "status": "pass" if schema_ok else ("needs_review" if not schema else "fail"),
        "detail": f"schema='{schema or 'undeclared'}' (supported: {', '.join(SUPPORTED_SCHEMAS)})",
    })

    storeys = model_info.get("storeys")
    checks.append({
        "check": "storeys_declared",
        "status": "pass" if isinstance(storeys, (int, float)) and storeys > 0 else "needs_review",
        "detail": f"storeys={storeys!r}",
    })

    units = model_info.get("length_unit")
    checks.append({
        "check": "length_unit_declared",
        "status": "pass" if units else "needs_review",
        "detail": f"length_unit={units!r}",
    })

    georef = model_info.get("georeferenced")
    checks.append({
        "check": "georeferencing",
        "status": "pass" if georef else "needs_review",
        "detail": f"georeferenced={georef!r}",
    })

    counts = model_info.get("entity_counts") or {}
    has_elements = any(counts.get(k, 0) > 0 for k in ("IfcWall", "IfcSlab", "IfcColumn", "IfcBeam"))
    checks.append({
        "check": "structural_elements_present",
        "status": "pass" if has_elements else "needs_review",
        "detail": f"entity_counts={counts}" if counts else "no entity counts provided",
    })

    failed = sum(1 for c in checks if c["status"] == "fail")
    pending = sum(1 for c in checks if c["status"] == "needs_review")
    status = "issues_found" if failed else ("incomplete_model_info" if pending else "container_checks_passed")

    return {
        "kind": "bim_review",
        "status": status,
        "checks": checks,
        "file": file_meta,
        "roadmap_capabilities": [
            "full IFC parsing and element extraction",
            "clash and completeness reporting",
            "mapping model quantities to preliminary code checks",
        ],
        "note_ar": "فحوصات أولية لحاوية النموذج فقط — ليست مراجعة اعتماد BIM رسمية.",
        "note_en": "Preliminary model-container checks only — not an official BIM approval review.",
        "disclaimer": disclaimer(),
    }
