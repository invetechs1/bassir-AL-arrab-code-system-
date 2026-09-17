"""Senior structural engineer agent.

Selects a concrete framing system for the span and storey count, sizes the
slab from span/depth ratios, runs a gravity load takedown to the worst
ground-floor column, and sizes that column and its footing. Durability
exposure is set from the city, because Eastern Province sulfate soils and
coastal chloride exposure drive cover and concrete grade.
"""

from app.agents.base import Agent, metric, note, rec, verify

# Indicative superimposed dead and live loads (kN/m2) by building type.
# Concept-stage figures for a load takedown sanity check — the design loads
# for a submission must come from SBC 301.
LOADS = {
    "villa": {"sdl": 2.5, "ll": 2.0},
    "apartment": {"sdl": 2.5, "ll": 2.0},
    "commercial": {"sdl": 3.0, "ll": 4.0},
    "mixed": {"sdl": 3.0, "ll": 3.0},
    "industrial": {"sdl": 3.5, "ll": 7.5},
}

CONCRETE_DENSITY = 25.0  # kN/m3
DEFAULT_BAY = 6.0        # m, typical economical RC bay

# Cities where coastal chloride or sulfate exposure drives durability.
COASTAL = ("جدة", "jeddah", "الدمام", "dammam", "الخبر", "khobar", "الجبيل", "jubail",
           "ينبع", "yanbu", "الظهران", "dhahran", "القطيف", "qatif", "رابغ", "rabigh")


def _exposure(city: str):
    low = (city or "").strip().lower()
    for token in COASTAL:
        if token in low:
            return "coastal"
    return "inland"


class StructuralAgent(Agent):
    agent_id = "structural"
    name_ar = "مهندس إنشائي أول"
    name_en = "Senior Structural Engineer"
    role_ar = "النظام الإنشائي، سماكات البلاطات، الأعمدة والأساسات، المواد والمتانة"
    role_en = "Framing system, slab depths, columns and foundations, materials and durability"
    depends_on = ("architecture",)

    def analyse(self, brief, ctx):
        floors = brief["floors"]
        btype = brief["building_type"]
        loads = LOADS.get(btype, LOADS["villa"])

        # Column grid: divide the envelope into bays no larger than DEFAULT_BAY.
        bays_w = max(1, int(-(-brief["build_w"] // DEFAULT_BAY)))
        bays_d = max(1, int(-(-brief["build_d"] // DEFAULT_BAY)))
        span_w = brief["build_w"] / bays_w
        span_d = brief["build_d"] / bays_d
        max_span = max(span_w, span_d)

        # System selection and the span/depth ratio that goes with it.
        if max_span <= 5.0:
            system_ar, system_en = "بلاطة مصمتة على جسور", "Solid slab on beams"
            ratio = 28.0
        elif max_span <= 7.5:
            system_ar, system_en = "بلاطة لا كمرية (فلات سلاب)", "RC flat slab"
            ratio = 33.0
        elif max_span <= 9.5:
            system_ar, system_en = "بلاطة لا كمرية مع تيجان أعمدة", "Flat slab with drop panels"
            ratio = 36.0
        else:
            system_ar, system_en = "بلاطة مسبقة الإجهاد", "Post-tensioned flat slab"
            ratio = 42.0

        # Slab thickness rounded up to the next 10 mm, 150 mm floor.
        slab_mm = max(150.0, -(-(max_span * 1000.0 / ratio) // 10) * 10)
        slab_kn_m2 = slab_mm / 1000.0 * CONCRETE_DENSITY

        # Gravity takedown on the worst internal column.
        tributary = span_w * span_d
        dead = slab_kn_m2 + loads["sdl"]
        service_per_floor = (dead + loads["ll"]) * tributary
        axial_service = service_per_floor * floors
        # 1.4 DL + 1.6 LL, the ordinary ultimate combination.
        axial_ultimate = ((1.4 * dead + 1.6 * loads["ll"]) * tributary) * floors

        # Column sizing: Ag >= N / (0.35 fcu) as a concept-stage short-column check.
        fcu = 30.0 if _exposure(brief["city"]) == "inland" else 35.0
        area_mm2 = axial_ultimate * 1000.0 / (0.35 * fcu)
        side_mm = max(250.0, -(-(area_mm2 ** 0.5) // 50) * 50)
        columns = (bays_w + 1) * (bays_d + 1)

        # Foundations against an assumed allowable bearing pressure.
        bearing_kpa = 150.0
        footing_area = axial_service / bearing_kpa
        footing_side = max(1.2, -(-(footing_area ** 0.5) * 10 // 1) / 10)
        total_footing_area = footing_area * columns
        raft = total_footing_area > 0.55 * brief["footprint"]

        exposure = _exposure(brief["city"])
        cover_mm = 50 if exposure == "coastal" else 40
        grade = "C35/45" if exposure == "coastal" else "C30/37"

        concrete_m3 = (
            brief["footprint"] * floors * slab_mm / 1000.0          # slabs
            + columns * (side_mm / 1000.0) ** 2 * brief["floor_h"] * floors  # columns
            + (total_footing_area * 0.6 if not raft else brief["footprint"] * 0.7)
        )
        rebar_tonnes = concrete_m3 * 0.11  # ~110 kg/m3 average across elements

        metrics = [
            metric("النظام الإنشائي", "Framing system", system_en, "", f"selected for a {max_span:.1f} m maximum span"),
            metric("الشبكة الإنشائية", "Structural grid", f"{bays_w}x{bays_d}", "bays",
                   f"{span_w:.2f} x {span_d:.2f} m, {DEFAULT_BAY:g} m target bay"),
            metric("أقصى بحر", "Maximum span", round(max_span, 2), "m", "longest clear bay"),
            metric("سماكة البلاطة", "Slab thickness", int(slab_mm), "mm", f"span/{ratio:g} rule of thumb"),
            metric("الحمل الميت الإضافي", "Superimposed dead load", loads["sdl"], "kN/m²", "indicative for this occupancy"),
            metric("الحمل الحي", "Live load", loads["ll"], "kN/m²", "indicative — confirm against SBC 301"),
            metric("حمل العمود (تشغيلي)", "Column axial load (service)", round(axial_service), "kN",
                   f"{tributary:.1f} m² tributary over {floors} floors"),
            metric("حمل العمود (أقصى)", "Column axial load (ultimate)", round(axial_ultimate), "kN", "1.4 DL + 1.6 LL"),
            metric("مقطع العمود التقديري", "Indicative column size", f"{int(side_mm)}x{int(side_mm)}", "mm",
                   f"Ag >= N / (0.35 x {fcu:g})"),
            metric("عدد الأعمدة", "Column count", columns, "", "grid intersections"),
            metric("نوع الأساسات", "Foundation type", "Raft" if raft else "Isolated pad footings", "",
                   f"{total_footing_area / brief['footprint'] * 100:.0f}% of footprint covered by pads"),
            metric("مقاس القاعدة المفردة", "Pad footing size", f"{footing_side:.1f}x{footing_side:.1f}", "m",
                   f"assumed {bearing_kpa:g} kPa allowable bearing"),
            metric("رتبة الخرسانة", "Concrete grade", grade, "", f"{exposure} exposure"),
            metric("الغطاء الخرساني", "Concrete cover", cover_mm, "mm", f"{exposure} exposure durability"),
            metric("حجم الخرسانة التقديري", "Indicative concrete volume", round(concrete_m3), "m³", "slabs, columns, foundations"),
            metric("وزن حديد التسليح", "Indicative reinforcement", round(rebar_tonnes, 1), "tonnes", "~110 kg/m³ average"),
        ]

        recommendations = [
            rec(f"اعتمد {system_ar} بسماكة {int(slab_mm)} مم لبحر {max_span:.1f} م.",
                f"Adopt a {system_en.lower()} at {int(slab_mm)} mm for the {max_span:.1f} m span.", "high"),
        ]
        if raft:
            recommendations.append(rec(
                "مساحة القواعد المفردة تتجاوز نصف البصمة — اللبشة (الراف) أوفر وأسهل تنفيذًا.",
                "Pad footings would cover more than half the footprint — a raft is more economical and simpler to build.",
                "high"))
        if exposure == "coastal":
            recommendations.append(rec(
                "الموقع ساحلي: ارفع رتبة الخرسانة والغطاء، واستخدم أسمنتًا مقاومًا للكبريتات مع اختبار تربة للكلوريدات والكبريتات.",
                "Coastal site: raise the concrete grade and cover, use sulfate-resisting cement, and test the soil for chlorides and sulfates.",
                "high"))
        recommendations.append(rec(
            f"الافتراض {bearing_kpa:g} ك.ن/م² لقدرة تحمل التربة مبدئي — لا تُنفّذ الأساسات قبل تقرير جسّ تربة معتمد.",
            f"The {bearing_kpa:g} kPa allowable bearing pressure is a placeholder — do not build foundations before an approved geotechnical report.",
            "high"))
        if floors >= 4:
            recommendations.append(rec(
                "من أربعة أدوار فأعلى ادرس مقاومة الأحمال الجانبية عبر جدران قص أو نواة، ولا تعتمد على الإطارات وحدها.",
                "At four storeys and above, resolve lateral loads with shear walls or a core rather than moment frames alone.",
                "high"))
        recommendations.append(rec(
            "حدّد فئة التصميم الزلزالي ومعاملات الموقع من SBC 301 حسب إحداثيات الموقع الفعلية.",
            "Establish the seismic design category and site coefficients from SBC 301 using the actual site coordinates.",
            "medium"))

        return {
            "summary_ar": (
                f"{system_ar} بسماكة {int(slab_mm)} مم على شبكة {bays_w}×{bays_d}، "
                f"أعمدة {int(side_mm)}×{int(side_mm)} مم و{'لبشة' if raft else 'قواعد منفصلة'}."
            ),
            "summary_en": (
                f"{system_en} at {int(slab_mm)} mm on a {bays_w}x{bays_d} grid, "
                f"{int(side_mm)}x{int(side_mm)} mm columns on {'a raft' if raft else 'isolated pad footings'}."
            ),
            "metrics": metrics,
            "schedule": [],
            "recommendations": recommendations,
            "assumptions": [
                note(f"قدرة تحمل التربة المفترضة {bearing_kpa:g} ك.ن/م² بدون تقرير جسّ تربة.",
                     f"An allowable bearing pressure of {bearing_kpa:g} kPa is assumed with no geotechnical report."),
                note("الأحمال الحية والميتة الإضافية قيم تخطيطية لنوع المبنى.",
                     "Live and superimposed dead loads are planning figures for this building type."),
                note("تحليل الأحمال الجانبية (الرياح والزلازل) خارج نطاق هذا التقدير.",
                     "Lateral load analysis for wind and seismic is outside the scope of this estimate."),
            ],
            "verify": [
                verify("الأحمال التصميمية ومعاملات الأمان وفئة التصميم الزلزالي.",
                       "Design loads, safety factors and the seismic design category.", "SBC 301"),
                verify("قدرة تحمل التربة ومنسوب التأسيس من تقرير جسّ معتمد.",
                       "Allowable bearing pressure and founding level from an approved geotechnical report.", "Site investigation"),
                verify("تفاصيل التسليح والمتانة ومقاومة الحريق للعناصر.",
                       "Reinforcement detailing, durability and element fire resistance.", "SBC 304 + SBC 801"),
            ],
            "outputs": {
                "slab_mm": int(slab_mm),
                "max_span_m": round(max_span, 2),
                "column_mm": int(side_mm),
                "columns": columns,
                "raft": raft,
                "concrete_m3": round(concrete_m3),
                "rebar_tonnes": round(rebar_tonnes, 1),
                "grade": grade,
                "exposure": exposure,
                "axial_service_kn": round(axial_service),
            },
        }
