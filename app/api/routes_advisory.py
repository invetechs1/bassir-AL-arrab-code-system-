"""Advisory endpoints: assistant, design, permit readiness, BIM, reports."""

import json

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import require
from app.api.schemas import (
    AssistantRequest, BimReviewRequest, DesignSuggestRequest,
    PermitReadinessRequest, ReportGenerateRequest,
)
from app.audit import log_action
from app.db.base import SessionLocal
from app.db.models import Report
from app.engine import bim_review, design_assistant, permit_readiness
from app.engine.reports import build_report
from app.governance.catalog import list_resources
from app.legal import disclaimer

router = APIRouter(prefix="/v1", tags=["advisory"])


@router.post("/assistant/suggest")
def assistant_suggest(body: AssistantRequest, principal=Depends(require("assistant:use"))):
    """Keyword-based guidance grounded in the regulatory source catalog.

    Honest MVP behavior: points the user to the relevant official sources
    and the platform features — it does not fabricate code values.
    """
    question = body.question.lower()
    topics = {
        "setback": ["ارتداد", "setback"],
        "fire": ["حريق", "دفاع مدني", "fire", "civil defense"],
        "permit": ["رخصة", "تصريح", "permit", "license", "بلدي", "balady"],
        "structure": ["إنشائي", "خرسانة", "structural", "concrete", "load"],
        "residential": ["سكني", "فيلا", "residential", "villa"],
    }
    matched = {t for t, words in topics.items() if any(w in question for w in words)}

    relevant = []
    for res in list_resources():
        blob = " ".join([res["title_ar"], res["title_en"], res["issuer"]]).lower()
        if ("fire" in matched and ("fire" in blob or "801" in res["id"])) or \
           ("permit" in matched and ("balady" in blob or "permit" in blob or "municipal" in blob)) or \
           ("structure" in matched and res["id"] in ("SBC-301", "SBC-302", "SBC-303", "SBC-304")) or \
           ("residential" in matched and res["id"] in ("SBC-1101", "SBC-1102")) or \
           ("setback" in matched and ("balady" in blob or "municipal" in blob or "201" in res["id"])):
            relevant.append({
                "id": res["id"], "title_ar": res["title_ar"], "title_en": res["title_en"],
                "source_reference": res["source_reference"], "status": res["status"],
            })
    if not relevant:
        relevant = [
            {"id": r["id"], "title_ar": r["title_ar"], "title_en": r["title_en"],
             "source_reference": r["source_reference"], "status": r["status"]}
            for r in list_resources() if r["priority"] == "P0"
        ]

    guidance = [
        {"ar": "استخدم «المراجعة الأولية» بإدخال معاملات المشروع للحصول على فحوصات المسودة.",
         "en": "Use the preliminary assessment with your project parameters to run the draft checks."},
        {"ar": "القيم النظامية الدقيقة تؤخذ حصريًا من الوثائق الرسمية المنشورة أدناه.",
         "en": "Exact regulatory values must be taken exclusively from the official publications listed below."},
    ]

    log_action(principal.tenant_id, principal.subject, "assistant.suggest")
    return {
        "kind": "assistant_guidance",
        "question": body.question,
        "matched_topics": sorted(matched),
        "guidance": guidance,
        "relevant_sources": relevant,
        "note_ar": "إرشاد أولي فقط — لا يقدم هذا المساعد قيمًا نظامية رسمية.",
        "note_en": "Preliminary guidance only — this assistant does not provide official regulatory values.",
        "disclaimer": disclaimer(),
    }


@router.post("/design/suggest")
def design_suggest(body: DesignSuggestRequest, principal=Depends(require("design:use"))):
    log_action(principal.tenant_id, principal.subject, "design.suggest")
    return design_assistant.suggest(body.model_dump(exclude_none=True))


@router.post("/permit/readiness")
def permit_readiness_endpoint(body: PermitReadinessRequest, principal=Depends(require("permit:use"))):
    log_action(principal.tenant_id, principal.subject, "permit.readiness")
    return permit_readiness.score(body.documents)


@router.post("/bim/review")
async def bim_review_endpoint(
    body: BimReviewRequest = None,
    principal=Depends(require("bim:use")),
):
    log_action(principal.tenant_id, principal.subject, "bim.review")
    return bim_review.review(model_info=(body.model_info if body else {}))


@router.post("/bim/review/file")
async def bim_review_file(
    file: UploadFile = File(...),
    principal=Depends(require("bim:use")),
):
    from app.api.routes_assess import _read_validated

    meta, content = await _read_validated(file)
    log_action(principal.tenant_id, principal.subject, "bim.review.file")
    return bim_review.review(filename=meta["original_filename"], content=content)


@router.post("/report/generate")
def report_generate(body: ReportGenerateRequest, principal=Depends(require("report:generate"))):
    report = build_report(body.model_dump(exclude_none=True))
    session = SessionLocal()
    try:
        session.add(
            Report(
                tenant_id=principal.tenant_id,
                title=report["title"],
                format="html+json",
                storage_path=json.dumps(report["files"]),
            )
        )
        session.commit()
    finally:
        session.close()
    log_action(principal.tenant_id, principal.subject, "report.generate", report["report_id"])
    return report
