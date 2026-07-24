"""Assessment endpoints: parameters, file, and vision."""

import hashlib
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import require
from app.api.schemas import AssessRequest
from app.audit import log_action
from app.config import settings
from app.db.base import SessionLocal
from app.db.models import Assessment, Upload
from app.engine.assessment import evaluate
from app.engine.file_analysis import analyze
from app.engine.vision import analyze_drawing
from app.legal import disclaimer
from app.security.uploads import UploadValidationError, validate_upload

router = APIRouter(prefix="/v1/assess", tags=["assess"])


def _persist_assessment(principal, kind: str, params: dict, result: dict) -> str:
    session = SessionLocal()
    try:
        record = Assessment(
            tenant_id=principal.tenant_id,
            kind=kind,
            input_json=json.dumps(params, ensure_ascii=False, default=str),
            result_json=json.dumps(result, ensure_ascii=False, default=str),
            score=float(result.get("score", 0) or 0),
            created_by=principal.subject,
        )
        session.add(record)
        session.commit()
        return record.id
    finally:
        session.close()


async def _read_validated(file: UploadFile) -> tuple:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"file exceeds {settings.max_upload_mb} MB limit")
    try:
        meta = validate_upload(file.filename or "", content)
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail={"en": exc.reason_en, "ar": exc.reason_ar})
    return meta, content


def _persist_upload(principal, meta: dict, content: bytes) -> None:
    settings.ensure_dirs()
    (settings.uploads_dir / meta["storage_name"]).write_bytes(content)
    session = SessionLocal()
    try:
        session.add(
            Upload(
                tenant_id=principal.tenant_id,
                original_filename=meta["original_filename"],
                storage_name=meta["storage_name"],
                extension=meta["extension"],
                size_bytes=meta["size_bytes"],
                sha256=hashlib.sha256(content).hexdigest(),
            )
        )
        session.commit()
    finally:
        session.close()


@router.post("")
def assess(body: AssessRequest, principal=Depends(require("assess:run"))):
    params = body.model_dump(exclude_none=True)
    rule_codes = params.pop("rule_codes", None)
    result = evaluate(params, rule_codes=rule_codes)
    assessment_id = _persist_assessment(principal, "parameters", params, result)
    result["assessment_id"] = assessment_id
    log_action(principal.tenant_id, principal.subject, "assess.run", assessment_id)
    return result


@router.post("/file")
async def assess_file(
    file: UploadFile = File(...),
    principal=Depends(require("assess:file")),
):
    meta, content = await _read_validated(file)
    _persist_upload(principal, meta, content)
    file_meta = analyze(meta["original_filename"], content)

    result = {
        "kind": "file_assessment_foundation",
        "status": "file_accepted",
        "file": file_meta,
        "storage_name": meta["storage_name"],
        "next_stage": "parameter extraction from drawings is on the roadmap; run POST /v1/assess with project parameters for the preliminary review",
        "note_ar": "تم قبول الملف وفحصه أمنيًا واستخراج بياناته الوصفية. استخراج المعاملات تلقائيًا قيد التطوير.",
        "note_en": "File accepted, security-scanned, and metadata extracted. Automatic parameter extraction is in development.",
        "disclaimer": disclaimer(),
    }
    assessment_id = _persist_assessment(principal, "file", {"filename": meta["original_filename"]}, result)
    result["assessment_id"] = assessment_id
    log_action(principal.tenant_id, principal.subject, "assess.file", assessment_id)
    return result


@router.post("/vision")
async def assess_vision(
    file: UploadFile = File(...),
    principal=Depends(require("assess:file")),
):
    meta, content = await _read_validated(file)
    _persist_upload(principal, meta, content)
    result = analyze_drawing(meta["original_filename"], content)
    result["storage_name"] = meta["storage_name"]
    assessment_id = _persist_assessment(principal, "vision", {"filename": meta["original_filename"]}, result)
    result["assessment_id"] = assessment_id
    log_action(principal.tenant_id, principal.subject, "assess.vision", assessment_id)
    return result
