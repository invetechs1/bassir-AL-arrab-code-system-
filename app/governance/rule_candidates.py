"""Rule-candidate governance workflow.

Pipeline: regulatory source -> rule CANDIDATE -> professional review ->
validated DRAFT rule (still inactive). Nothing in this module can
activate a rule or mark it official; activation is a deliberate,
separate operational step after professional sign-off.
"""

from datetime import date

from app.governance.catalog import NON_BINDING_STATUSES, list_resources
from app.legal import disclaimer

REQUIRED_REVIEW_FIELDS = (
    "clause",
    "last_reviewed_date",
    "confidence_level",
    "validated_by",
)

ALLOWED_CONFIDENCE = ("low", "medium", "high")


def generate_candidates() -> list:
    """Derive rule candidates from catalog sources.

    Draft/consultation sources still produce candidates (for tracking)
    but are hard-flagged non-exportable.
    """
    candidates = []
    for res in list_resources():
        from_non_binding = res["status"] in NON_BINDING_STATUSES or not res["binding"]
        candidates.append({
            "candidate_id": f"CAND-{res['id']}",
            "resource_id": res["id"],
            "resource_title_ar": res["title_ar"],
            "resource_title_en": res["title_en"],
            "issuer": res["issuer"],
            "priority": res["priority"],
            "source_status": res["status"],
            "source_reference": res["source_reference"],
            "exportable": not from_non_binding,
            "non_binding_source": from_non_binding,
            "review_status": "pending_professional_review",
            "required_before_validation": list(REQUIRED_REVIEW_FIELDS),
            "note_ar": (
                "مصدر غير ملزم (مسودة/استطلاع) — للمتابعة فقط ولا يمكن تصديره كقاعدة."
                if from_non_binding
                else "بانتظار مراجعة مهنية: يجب توثيق البند الدقيق من الوثيقة الرسمية."
            ),
            "note_en": (
                "Non-binding source (draft/consultation) — tracked only, can never be exported as a rule."
                if from_non_binding
                else "Pending professional review: the exact clause must be documented from the official publication."
            ),
        })
    return candidates


def review_package() -> dict:
    candidates = generate_candidates()
    return {
        "kind": "rule_candidate_review_package",
        "instructions_ar": [
            "راجع كل مرشح مقابل الوثيقة الرسمية المنشورة (وليس هذا النظام).",
            "وثّق رقم البند الدقيق (clause) وتاريخ المراجعة ومستوى الثقة.",
            "أدخل اسم ورقم ترخيص المهندس المعتمد في حقل validated_by.",
            "القرار approve ينتج قاعدة مسودة غير مفعّلة — التفعيل خطوة تشغيلية منفصلة.",
        ],
        "instructions_en": [
            "Review each candidate against the official published document (not this system).",
            "Record the exact clause number, review date, and confidence level.",
            "Enter the licensed professional's name and license number in validated_by.",
            "An 'approve' decision produces an INACTIVE draft rule — activation is a separate operational step.",
        ],
        "required_fields": list(REQUIRED_REVIEW_FIELDS),
        "allowed_confidence_levels": list(ALLOWED_CONFIDENCE),
        "candidates": candidates,
        "disclaimer": disclaimer(),
    }


def _candidate_index() -> dict:
    return {c["candidate_id"]: c for c in generate_candidates()}


def validate_reviews(reviews: list) -> dict:
    """Validate submitted professional reviews. Pure validation — no persistence."""
    index = _candidate_index()
    results = []
    for review in reviews or []:
        cid = review.get("candidate_id", "")
        candidate = index.get(cid)
        problems = []

        if candidate is None:
            results.append({"candidate_id": cid, "outcome": "unknown_candidate", "problems": ["candidate not found"]})
            continue
        if candidate["non_binding_source"]:
            results.append({
                "candidate_id": cid,
                "outcome": "rejected_non_binding_source",
                "problems": ["draft/consultation sources can never be validated into rules"],
            })
            continue

        for field in REQUIRED_REVIEW_FIELDS:
            if not review.get(field):
                problems.append(f"missing required field '{field}'")
        if review.get("confidence_level") and review["confidence_level"] not in ALLOWED_CONFIDENCE:
            problems.append(f"confidence_level must be one of {ALLOWED_CONFIDENCE}")
        raw_date = review.get("last_reviewed_date", "")
        if raw_date:
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                problems.append("last_reviewed_date must be ISO format YYYY-MM-DD")
        decision = review.get("decision", "")
        if decision not in ("approve", "reject"):
            problems.append("decision must be 'approve' or 'reject'")

        if problems:
            outcome = "incomplete"
        elif decision == "reject":
            outcome = "rejected_by_reviewer"
        else:
            outcome = "validated_draft"
        results.append({"candidate_id": cid, "outcome": outcome, "problems": problems})

    return {
        "kind": "rule_candidate_validation",
        "results": results,
        "validated_count": sum(1 for r in results if r["outcome"] == "validated_draft"),
        "disclaimer": disclaimer(),
    }


def export_draft_rules(reviews: list) -> dict:
    """Export validated reviews as DRAFT rules. is_active is always False."""
    validation = validate_reviews(reviews)
    validated_ids = {
        r["candidate_id"] for r in validation["results"] if r["outcome"] == "validated_draft"
    }
    index = _candidate_index()
    review_by_id = {r.get("candidate_id"): r for r in reviews or []}

    draft_rules = []
    for cid in sorted(validated_ids):
        candidate = index[cid]
        review = review_by_id[cid]
        draft_rules.append({
            "code": f"DRAFT-{candidate['resource_id']}-{review.get('rule_suffix', '001')}",
            "title_ar": review.get("title_ar", candidate["resource_title_ar"]),
            "title_en": review.get("title_en", candidate["resource_title_en"]),
            "category": review.get("category", "uncategorized"),
            "check": review.get("check", {}),
            "status": "validated_draft",
            "is_active": False,  # invariant: exported rules are NEVER active
            "is_official": False,  # activation + official designation is a separate operational decision
            "governance": {
                "source_reference": candidate["source_reference"],
                "clause": review["clause"],
                "last_reviewed_date": review["last_reviewed_date"],
                "confidence_level": review["confidence_level"],
                "validated_by": review["validated_by"],
            },
        })

    return {
        "kind": "draft_rules_export",
        "draft_rules": draft_rules,
        "exported_count": len(draft_rules),
        "skipped": [r for r in validation["results"] if r["outcome"] != "validated_draft"],
        "note_ar": "جميع القواعد المصدّرة مسودات غير مفعّلة. التفعيل قرار تشغيلي منفصل بعد الاعتماد المهني.",
        "note_en": "All exported rules are inactive drafts. Activation is a separate operational decision after professional sign-off.",
        "disclaimer": disclaimer(),
    }
