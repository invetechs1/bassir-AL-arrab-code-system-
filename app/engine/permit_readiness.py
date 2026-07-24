"""Permit-readiness scoring based on the standard document checklist."""

from app.legal import disclaimer

CHECKLIST = [
    {"key": "title_deed", "ar": "صك الملكية الإلكتروني", "en": "Electronic title deed", "weight": 3},
    {"key": "survey_report", "ar": "الرفع المساحي / تقرير المساح", "en": "Survey report", "weight": 3},
    {"key": "soil_report", "ar": "تقرير فحص التربة", "en": "Soil investigation report", "weight": 2},
    {"key": "architectural_drawings", "ar": "المخططات المعمارية", "en": "Architectural drawings", "weight": 3},
    {"key": "structural_drawings", "ar": "المخططات الإنشائية", "en": "Structural drawings", "weight": 3},
    {"key": "mep_drawings", "ar": "مخططات الكهروميكانيك", "en": "MEP drawings", "weight": 2},
    {"key": "energy_compliance", "ar": "متطلبات كفاءة الطاقة", "en": "Energy-efficiency compliance", "weight": 1},
    {"key": "civil_defense_requirements", "ar": "متطلبات الدفاع المدني (حسب النشاط)", "en": "Civil Defense requirements (activity-dependent)", "weight": 2},
    {"key": "engineering_office_contract", "ar": "عقد مكتب هندسي مرخص", "en": "Licensed engineering office contract", "weight": 3},
    {"key": "contractor_classification", "ar": "تصنيف المقاول (إن وجد)", "en": "Contractor classification (if applicable)", "weight": 1},
]


def score(documents: dict) -> dict:
    total = sum(item["weight"] for item in CHECKLIST)
    achieved = 0
    provided, missing = [], []

    for item in CHECKLIST:
        entry = {"key": item["key"], "ar": item["ar"], "en": item["en"], "weight": item["weight"]}
        if bool(documents.get(item["key"])):
            achieved += item["weight"]
            provided.append(entry)
        else:
            missing.append(entry)

    readiness = round(100.0 * achieved / total, 1)
    if readiness >= 90:
        level = "ready_for_submission_review"
    elif readiness >= 60:
        level = "nearly_ready"
    else:
        level = "early_stage"

    next_steps = [
        {"ar": f"استكمال: {m['ar']}", "en": f"Provide: {m['en']}"} for m in missing[:5]
    ]
    next_steps.append({
        "ar": "التقديم الرسمي يتم فقط عبر منصة بلدي بواسطة مكتب هندسي مرخص.",
        "en": "Official submission happens only via the Balady platform through a licensed engineering office.",
    })

    return {
        "kind": "permit_readiness",
        "readiness_score": readiness,
        "readiness_level": level,
        "provided": provided,
        "missing": missing,
        "next_steps": next_steps,
        "note_ar": "مؤشر جاهزية استرشادي — القبول النهائي تحدده البلدية والجهات المختصة.",
        "note_en": "Indicative readiness score — final acceptance is determined by the municipality and competent authorities.",
        "disclaimer": disclaimer(),
    }
