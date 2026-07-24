"""Deterministic preliminary assessment engine.

Evaluates project parameters against the draft rule set and returns
structured findings. Every result is labeled preliminary/draft and
carries the mandatory disclaimer.
"""

from app.engine.rules_store import list_rules
from app.legal import disclaimer

SEVERITY_WEIGHTS = {"high": 3.0, "medium": 2.0, "low": 1.0}

NUMERIC_FIELDS = (
    "plot_area_m2", "floors", "building_height_m", "setback_front_m",
    "setback_side_m", "setback_rear_m", "coverage_ratio", "far",
    "parking_spaces", "units",
)


def _to_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _evaluate_check(check: dict, params: dict):
    """Return (status, detail). status: pass | fail | needs_review."""
    ctype = check.get("type")
    field = check.get("field")
    value = check.get("value")

    if ctype in ("min", "max"):
        actual = _to_number(params.get(field))
        if actual is None:
            return "needs_review", f"missing input '{field}'"
        if ctype == "min":
            ok = actual >= value
            relation = ">="
        else:
            ok = actual <= value
            relation = "<="
        detail = f"{field}={actual:g} (draft check: {relation} {value:g} {check.get('unit', '')})".strip()
        return ("pass" if ok else "fail"), detail

    if ctype == "min_ratio":
        numerator = _to_number(params.get(field))
        denominator = _to_number(params.get(check.get("per_field")))
        if numerator is None or denominator is None:
            return "needs_review", f"missing input '{field}' or '{check.get('per_field')}'"
        if denominator <= 0:
            return "needs_review", f"'{check.get('per_field')}' must be > 0"
        ratio = numerator / denominator
        ok = ratio >= value
        detail = f"{field}/{check.get('per_field')}={ratio:.2f} (draft check: >= {value:g})"
        return ("pass" if ok else "fail"), detail

    if ctype == "required_enum":
        actual = params.get(field)
        allowed = check.get("values", [])
        if actual in (None, ""):
            return "needs_review", f"missing input '{field}'"
        if actual in allowed:
            return "pass", f"{field}='{actual}'"
        return "fail", f"{field}='{actual}' not in {allowed}"

    return "needs_review", f"unknown check type '{ctype}'"


def evaluate(params: dict, rule_codes=None) -> dict:
    findings = []
    total_weight = 0.0
    passed_weight = 0.0
    counts = {"pass": 0, "fail": 0, "needs_review": 0}

    for rule in list_rules():
        if rule_codes and rule["code"] not in rule_codes:
            continue
        status, detail = _evaluate_check(rule.get("check", {}), params)
        counts[status] += 1
        weight = SEVERITY_WEIGHTS.get(rule.get("severity", "medium"), 2.0)
        if status != "needs_review":
            total_weight += weight
            if status == "pass":
                passed_weight += weight
        findings.append({
            "rule_code": rule["code"],
            "title_ar": rule["title_ar"],
            "title_en": rule["title_en"],
            "category": rule["category"],
            "severity": rule.get("severity", "medium"),
            "status": status,
            "detail": detail,
            "is_official": rule["is_official"],
            "governance": rule.get("governance", {}),
        })

    score = round(100.0 * passed_weight / total_weight, 1) if total_weight else 0.0
    if counts["fail"] > 0:
        overall = "issues_found"
    elif counts["needs_review"] > 0:
        overall = "incomplete_input"
    else:
        overall = "preliminary_pass"

    return {
        "kind": "preliminary_assessment",
        "overall_status": overall,
        "score": score,
        "counts": counts,
        "findings": findings,
        "input_echo": {k: params.get(k) for k in (*NUMERIC_FIELDS, "land_use", "city", "project_name") if k in params},
        "official_basis": False,
        "note_ar": "نتيجة أولية اعتمادًا على قواعد تحقق تجريبية (مسودة) — ليست فحصًا رسميًا.",
        "note_en": "Preliminary result based on DRAFT verification rules — not an official review.",
        "disclaimer": disclaimer(),
    }
