"""Heuristic design assistant. Advisory output only — never a code ruling."""

from app.legal import disclaimer


def _num(params, key):
    try:
        return float(params.get(key))
    except (TypeError, ValueError):
        return None


def suggest(params: dict) -> dict:
    plot = _num(params, "plot_area_m2")
    floors = _num(params, "floors") or 2
    coverage = _num(params, "coverage_ratio") or 0.6
    land_use = params.get("land_use", "residential")

    suggestions = []
    estimates = {}

    if plot:
        footprint = plot * min(coverage, 0.6)
        estimates["indicative_footprint_m2"] = round(footprint, 1)
        estimates["indicative_gross_floor_area_m2"] = round(footprint * floors, 1)
        suggestions.append({
            "ar": f"بمساحة أرض {plot:g} م² ونسبة تغطية استرشادية {min(coverage, 0.6):.0%}، "
                  f"البصمة البنائية الاسترشادية ≈ {footprint:.0f} م².",
            "en": f"With a {plot:g} m² plot and an indicative coverage of {min(coverage, 0.6):.0%}, "
                  f"the indicative footprint is ≈ {footprint:.0f} m².",
        })
    else:
        suggestions.append({
            "ar": "أدخل مساحة الأرض للحصول على تقديرات البصمة البنائية والمسطحات.",
            "en": "Provide the plot area to receive footprint and floor-area estimates.",
        })

    suggestions.append({
        "ar": "تحقق من اشتراطات النطاق العمراني للأرض عبر منصة بلدي قبل اعتماد أي توزيع تصميمي.",
        "en": "Verify the plot's zoning requirements on the Balady platform before committing to any layout.",
    })
    if land_use == "residential":
        suggestions.append({
            "ar": "راعِ توجيه المجالس والنوافذ الرئيسية بعيدًا عن الواجهات الغربية لتقليل الأحمال الحرارية.",
            "en": "Consider orienting main living spaces away from western facades to reduce thermal loads.",
        })

    return {
        "kind": "design_suggestions",
        "advisory_only": True,
        "estimates": estimates,
        "suggestions": suggestions,
        "note_ar": "اقتراحات استرشادية فقط وليست تصميمًا هندسيًا معتمدًا.",
        "note_en": "Indicative suggestions only — not an approved engineering design.",
        "disclaimer": disclaimer(),
    }
