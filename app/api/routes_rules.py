"""Rules, regulatory resources, and the rule-candidate governance workflow."""

from fastapi import APIRouter, Depends

from app.api.deps import require
from app.api.schemas import CandidateReviewBatch
from app.audit import log_action
from app.engine.rules_store import list_rules
from app.governance import rule_candidates
from app.governance.catalog import list_resources, summary
from app.legal import disclaimer

router = APIRouter(prefix="/v1", tags=["rules", "governance"])


@router.get("/rules")
def get_rules(principal=Depends(require("rules:read"))):
    rules = list_rules()
    return {
        "count": len(rules),
        "official_count": sum(1 for r in rules if r["is_official"]),
        "rules": rules,
        "note_ar": "جميع القواعد الحالية مسودات غير رسمية وغير مفعّلة حتى الاعتماد المهني.",
        "note_en": "All current rules are non-official inactive drafts until professional validation.",
        "disclaimer": disclaimer(),
    }


@router.get("/regulatory-resources")
def regulatory_resources(principal=Depends(require("governance:read"))):
    return {"resources": list_resources(), "disclaimer": disclaimer()}


@router.get("/regulatory-resources/summary")
def regulatory_resources_summary(principal=Depends(require("governance:read"))):
    return summary()


@router.get("/rule-candidates/from-resources")
def candidates_from_resources(principal=Depends(require("governance:read"))):
    candidates = rule_candidates.generate_candidates()
    return {
        "count": len(candidates),
        "exportable_count": sum(1 for c in candidates if c["exportable"]),
        "candidates": candidates,
        "disclaimer": disclaimer(),
    }


@router.get("/rule-candidates/review-package")
def candidates_review_package(principal=Depends(require("governance:review"))):
    return rule_candidates.review_package()


@router.post("/rule-candidates/review/validate")
def candidates_validate(body: CandidateReviewBatch, principal=Depends(require("governance:review"))):
    log_action(principal.tenant_id, principal.subject, "governance.validate_reviews")
    return rule_candidates.validate_reviews(body.reviews)


@router.post("/rule-candidates/review/export-draft-rules")
def candidates_export(body: CandidateReviewBatch, principal=Depends(require("governance:export"))):
    log_action(principal.tenant_id, principal.subject, "governance.export_draft_rules")
    return rule_candidates.export_draft_rules(body.reviews)
