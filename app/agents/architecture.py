"""Senior architecture engineer agent.

Sits first in the chain: it fixes the envelope, the area budget and the
core, which every other discipline then sizes against. Produces a space
program, an efficiency split, an egress sanity check and a climate
response for the hot-arid Saudi context.
"""

from app.agents.base import Agent, metric, note, rec, verify

# Indicative planning densities (m2 of gross floor area per occupant).
# Concept-stage planning figures for sizing circulation and egress only —
# the occupant load used for a Civil Defence submission must be taken from
# SBC 801 for the actual occupancy classification.
OCCUPANT_DENSITY_M2 = {
    "villa": 30.0,
    "apartment": 25.0,
    "commercial": 10.0,
    "mixed": 15.0,
    "industrial": 50.0,
}

# Indicative net-to-gross efficiency by building type.
NET_TO_GROSS = {
    "villa": 0.82,
    "apartment": 0.76,
    "commercial": 0.80,
    "mixed": 0.78,
    "industrial": 0.88,
}

# Space program weights per building type: (ar, en, share of net area).
PROGRAMS = {
    "villa": [
        ("مجلس رجال", "Men's majlis", 0.13),
        ("مجلس نساء", "Women's majlis", 0.10),
        ("صالة معيشة", "Family living", 0.15),
        ("مطبخ", "Kitchen", 0.09),
        ("غرفة طعام", "Dining", 0.09),
        ("غرف نوم", "Bedrooms", 0.30),
        ("دورات مياه", "Bathrooms", 0.08),
        ("خدمات وتخزين", "Services and storage", 0.06),
    ],
    "apartment": [
        ("صالة معيشة", "Living room", 0.22),
        ("مطبخ", "Kitchen", 0.11),
        ("غرف نوم", "Bedrooms", 0.38),
        ("دورات مياه", "Bathrooms", 0.11),
        ("مجلس/استقبال", "Reception", 0.12),
        ("خدمات وتخزين", "Services and storage", 0.06),
    ],
    "commercial": [
        ("مساحات تأجيرية", "Lettable area", 0.62),
        ("استقبال ولوبي", "Reception and lobby", 0.12),
        ("دورات مياه", "Toilets", 0.08),
        ("مخازن", "Storage", 0.08),
        ("غرف خدمات فنية", "Plant and service rooms", 0.10),
    ],
    "mixed": [
        ("محلات تجارية أرضية", "Ground-floor retail", 0.30),
        ("وحدات سكنية", "Residential units", 0.44),
        ("استقبال ومداخل", "Lobbies and entrances", 0.10),
        ("دورات مياه", "Toilets", 0.06),
        ("غرف خدمات فنية", "Plant and service rooms", 0.10),
    ],
    "industrial": [
        ("صالة إنتاج", "Production hall", 0.62),
        ("مستودعات", "Warehousing", 0.20),
        ("مكاتب إدارية", "Administration offices", 0.10),
        ("خدمات وعمال", "Staff and welfare", 0.08),
    ],
}


def _program_for(building_type):
    return PROGRAMS.get(building_type, PROGRAMS["villa"])


class ArchitectureAgent(Agent):
    agent_id = "architecture"
    name_ar = "مهندس معماري أول"
    name_en = "Senior Architecture Engineer"
    role_ar = "الكتلة البنائية، البرنامج المساحي، الحركة والمخارج، معالجة المناخ"
    role_en = "Massing, space program, circulation and egress, climate response"
    depends_on = ()

    def analyse(self, brief, ctx):
        gfa = brief["gfa"]
        floors = brief["floors"]
        btype = brief["building_type"]

        efficiency = NET_TO_GROSS.get(btype, 0.80)
        net_area = gfa * efficiency
        circulation = gfa - net_area

        density = OCCUPANT_DENSITY_M2.get(btype, 30.0)
        occupants = max(1, int(round(gfa / density))) if density else 1

        # Egress sanity check. Two exits are the ordinary expectation once
        # an occupant load passes ~50; the binding trigger is SBC 801.
        exits_required = 1 if occupants <= 49 else (2 if occupants <= 500 else 3)
        # 7.6 mm of stair width per occupant is the common planning figure.
        stair_width_mm = max(1100.0, occupants * 7.6 / max(1, exits_required))

        # Core: stairs plus lift lobby where the building warrants a lift.
        lift_required = floors >= 4
        lifts = 1 if lift_required else 0
        if lift_required and occupants > 120:
            lifts = 2
        core_area = (stair_width_mm / 1000.0 * 5.5) * exits_required + (lifts * 6.0)

        metrics = [
            metric("البصمة البنائية", "Building footprint", round(brief["footprint"], 1), "m²",
                   "plot minus entered setbacks"),
            metric("إجمالي المسطحات", "Gross floor area", round(gfa, 1), "m²",
                   "footprint x floors"),
            metric("المساحة الصافية", "Net usable area", round(net_area, 1), "m²",
                   f"indicative net:gross {efficiency:.2f} for {btype}"),
            metric("مساحة الحركة والخدمات", "Circulation and services", round(circulation, 1), "m²",
                   "gross minus net"),
            metric("نسبة التغطية", "Site coverage", round(brief["coverage"], 3), "",
                   "footprint / plot area"),
            metric("معامل البناء", "Floor area ratio", round(brief["far"], 3), "",
                   "gross floor area / plot area"),
            metric("الإشغال التقديري", "Estimated occupant load", occupants, "persons",
                   f"indicative {density:g} m²/person planning density"),
            metric("عدد المخارج المطلوبة", "Exits required", exits_required, "",
                   "planning check on occupant load — confirm against SBC 801"),
            metric("عرض الدرج الصافي", "Clear stair width", round(stair_width_mm), "mm",
                   "7.6 mm per occupant, 1100 mm minimum"),
            metric("مساحة النواة التقديرية", "Indicative core area", round(core_area, 1), "m²",
                   "stairs plus lift lobby"),
        ]

        schedule = []
        for ar, en, share in _program_for(btype):
            area = net_area * share
            schedule.append({
                "ar": ar,
                "en": en,
                "area_m2": round(area, 1),
                "share": round(share, 3),
                "per_floor_m2": round(area / floors, 1) if floors else round(area, 1),
            })

        recommendations = []
        if brief["coverage"] > 0.60:
            recommendations.append(rec(
                f"نسبة التغطية {brief['coverage']:.2f} تتجاوز حد المسودة ٠٫٦٠ — قلّص البصمة أو زد الارتداد الجانبي/الخلفي.",
                f"Site coverage of {brief['coverage']:.2f} exceeds the 0.60 draft limit — reduce the footprint or increase the side/rear setback.",
                "high"))
        if lift_required:
            recommendations.append(rec(
                f"المبنى {floors} أدوار — خصّص {lifts} مصعدًا وبئر مصعد ضمن النواة، وراجع اشتراطات إمكانية الوصول.",
                f"At {floors} floors the building needs {lifts} lift(s) and a shaft inside the core; review accessibility requirements.",
                "high"))
        if exits_required >= 2:
            recommendations.append(rec(
                f"الإشغال التقديري {occupants} شخصًا يستدعي {exits_required} مخارج منفصلة بمسافات انتقال متوافقة — اعتمد التصميم من الدفاع المدني.",
                f"An estimated occupant load of {occupants} calls for {exits_required} separate exits with compliant travel distances — the design needs Civil Defence approval.",
                "high"))
        recommendations.append(rec(
            "وجّه الفتحات الرئيسية شمالًا وشمالًا شرقيًا، وقلّل نسبة الزجاج على الواجهة الغربية إلى أقل من ٢٥٪ مع كاسرات شمس أفقية.",
            "Orient primary openings north and north-east, and hold the west facade below a 25% window-to-wall ratio with horizontal shading.",
            "medium"))
        recommendations.append(rec(
            "احجز فناءً داخليًا أو منورًا للتهوية والإضاءة الطبيعية للغرف الداخلية في العمق البنائي الكبير.",
            "Reserve an internal courtyard or light well to ventilate and daylight the inner rooms in the deep floor plate.",
            "medium"))
        if brief["build_d"] > 18:
            recommendations.append(rec(
                f"عمق المبنى {brief['build_d']:.1f} م كبير على إضاءة طبيعية أحادية الجانب — اعتمد منورًا أو فناءً.",
                f"A {brief['build_d']:.1f} m building depth is too deep for single-sided daylight — introduce a light well or courtyard.",
                "medium"))

        assumptions = [
            note("البصمة مستطيلة تملأ كامل الظرف القابل للبناء بعد الارتدادات.",
                 "The footprint is rectangular and fills the whole buildable envelope after setbacks."),
            note(f"نسبة الصافي إلى الإجمالي {efficiency:.2f} مأخوذة كقيمة تخطيطية لنوع المبنى.",
                 f"A {efficiency:.2f} net-to-gross ratio is assumed as a planning figure for this building type."),
            note("كثافة الإشغال تخطيطية لتحديد الحركة والمخارج فقط.",
                 "The occupancy density is a planning figure used only to size circulation and egress."),
        ]

        return {
            "summary_ar": (
                f"مسطح إجمالي {gfa:,.0f} م² على {floors} أدوار، منها {net_area:,.0f} م² صافية "
                f"و{circulation:,.0f} م² حركة وخدمات، بإشغال تقديري {occupants} شخصًا."
            ),
            "summary_en": (
                f"{gfa:,.0f} m² gross over {floors} floors — {net_area:,.0f} m² net and "
                f"{circulation:,.0f} m² circulation and services, at an estimated occupant load of {occupants}."
            ),
            "metrics": metrics,
            "schedule": schedule,
            "recommendations": recommendations,
            "assumptions": assumptions,
            "verify": [
                verify("حمل الإشغال وعدد المخارج ومسافات الانتقال وعرض الأدراج.",
                       "Occupant load, exit count, travel distances and stair widths.",
                       "SBC 801 + Civil Defence"),
                verify("نسبة التغطية ومعامل البناء والارتفاع المسموح للقطعة.",
                       "Permitted site coverage, floor area ratio and height for this plot.",
                       "Balady zoning for the specific plot"),
                verify("اشتراطات إمكانية الوصول والمصاعد.",
                       "Accessibility and lift requirements.",
                       "SBC 201 + accessibility code"),
            ],
            "outputs": {
                "net_area_m2": round(net_area, 1),
                "efficiency": efficiency,
                "occupants": occupants,
                "exits_required": exits_required,
                "core_area_m2": round(core_area, 1),
                "lifts": lifts,
            },
        }
