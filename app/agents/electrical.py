"""Senior electrical engineer agent.

Builds a connected-load schedule, applies diversity, and sizes the incoming
service. The HVAC share comes from the mechanical agent, because in this
climate cooling is usually the largest single block of the electrical load
and sizing the service without it understates the supply badly.
"""

from app.agents.base import Agent, metric, note, rec, verify

# Indicative connected load allowances, VA per m2 of gross floor area,
# excluding HVAC (which is taken from the mechanical agent).
LOAD_VA_M2 = {
    "villa": {"lighting": 8.0, "power": 25.0, "misc": 6.0},
    "apartment": {"lighting": 8.0, "power": 22.0, "misc": 6.0},
    "commercial": {"lighting": 12.0, "power": 35.0, "misc": 10.0},
    "mixed": {"lighting": 10.0, "power": 28.0, "misc": 8.0},
    "industrial": {"lighting": 10.0, "power": 60.0, "misc": 12.0},
}

# Indicative diversity factors applied to each block.
DIVERSITY = {"lighting": 0.90, "power": 0.70, "misc": 0.80, "hvac": 0.85}

# Indicative maintained illuminance, lux, by space.
LUX = [
    ("مجلس واستقبال", "Majlis and reception", 200),
    ("صالة معيشة", "Living area", 150),
    ("غرف نوم", "Bedrooms", 150),
    ("مطبخ", "Kitchen", 300),
    ("دورات مياه", "Bathrooms", 150),
    ("ممرات ودرج", "Corridors and stairs", 100),
    ("مكاتب", "Offices", 500),
    ("مواقف ومخازن", "Parking and storage", 75),
]

SQRT3 = 1.7320508075688772
LINE_VOLTAGE = 400.0  # V, three phase


class ElectricalAgent(Agent):
    agent_id = "electrical"
    name_ar = "مهندس كهربائي أول"
    name_en = "Senior Electrical Engineer"
    role_ar = "أحمال الكهرباء، حجم التغذية، اللوحات والتوزيع، الإنارة، التأريض"
    role_en = "Electrical loads, service sizing, boards and distribution, lighting, earthing"
    depends_on = ("architecture", "mechanical")

    def analyse(self, brief, ctx):
        gfa = brief["gfa"]
        btype = brief["building_type"]
        units = brief["units"]
        floors = brief["floors"]

        allowances = LOAD_VA_M2.get(btype, LOAD_VA_M2["villa"])
        mech = ctx.get("mechanical", {}).get("outputs", {})
        # HVAC electrical input: about 1.1 kW per TR for an efficient system.
        hvac_kw = (mech.get("tons") or gfa / 20.0) * 1.1

        blocks = []
        connected_kva = 0.0
        demand_kva = 0.0
        for key in ("lighting", "power", "misc"):
            connected = allowances[key] * gfa / 1000.0  # kVA
            demand = connected * DIVERSITY[key]
            connected_kva += connected
            demand_kva += demand
            blocks.append({
                "key": key,
                "ar": {"lighting": "الإنارة", "power": "القوى والمقابس", "misc": "أحمال متنوعة"}[key],
                "en": {"lighting": "Lighting", "power": "Power and sockets", "misc": "Miscellaneous"}[key],
                "connected_kva": round(connected, 1),
                "diversity": DIVERSITY[key],
                "demand_kva": round(demand, 1),
            })
        hvac_kva = hvac_kw / 0.9  # assumed power factor
        connected_kva += hvac_kva
        demand_kva += hvac_kva * DIVERSITY["hvac"]
        blocks.append({
            "key": "hvac",
            "ar": "التكييف",
            "en": "HVAC",
            "connected_kva": round(hvac_kva, 1),
            "diversity": DIVERSITY["hvac"],
            "demand_kva": round(hvac_kva * DIVERSITY["hvac"], 1),
        })

        # Main breaker from the diversified demand, three phase at 400 V.
        current_a = demand_kva * 1000.0 / (SQRT3 * LINE_VOLTAGE)
        standard = [63, 100, 125, 160, 200, 250, 320, 400, 500, 630, 800, 1000, 1250, 1600, 2000]
        breaker = next((s for s in standard if s >= current_a * 1.15), standard[-1])

        # A dedicated transformer or substation becomes likely past ~100 kVA.
        transformer = demand_kva > 100
        substation_area = 0.0
        if transformer:
            substation_area = 20.0 if demand_kva <= 500 else 35.0

        # Distribution boards: one per unit, plus landlord and per-floor boards.
        boards = units + max(1, floors) + 1
        circuits = int(gfa / 25) + units * 6

        metrics = [
            metric("الحمل المركب", "Connected load", round(connected_kva, 1), "kVA", "sum of all load blocks"),
            metric("الحمل المقدّر", "Diversified demand", round(demand_kva, 1), "kVA", "after diversity factors"),
            metric("حمل التكييف الكهربائي", "HVAC electrical input", round(hvac_kw, 1), "kW",
                   f"~1.1 kW/TR on {mech.get('tons', 0):.0f} TR from the mechanical agent"),
            metric("كثافة الحمل", "Load density", round(demand_kva * 1000 / gfa, 1), "VA/m²", "demand per gross m²"),
            metric("تيار التغذية", "Service current", round(current_a), "A", "three phase at 400 V"),
            metric("قاطع رئيسي", "Main breaker", breaker, "A", "next standard rating above 115% of demand"),
            metric("محول مخصص", "Dedicated transformer", "Required" if transformer else "Not indicated", "",
                   "indicative threshold at 100 kVA — confirm with SEC"),
            metric("مساحة غرفة المحول", "Substation room area", round(substation_area, 1), "m²",
                   "SEC layout requirement" if transformer else "not applicable"),
            metric("عدد لوحات التوزيع", "Distribution boards", boards, "", "per unit, per floor, plus landlord services"),
            metric("عدد الدوائر التقديري", "Indicative final circuits", circuits, "", "planning estimate"),
            metric("مقاومة التأريض", "Earthing resistance", "<= 1", "ohm", "SEC expectation — verify on site"),
        ]

        schedule = [
            {"ar": ar, "en": en, "lux": lux, "note_en": "maintained illuminance"}
            for ar, en, lux in LUX
        ]

        recommendations = [
            rec(f"اطلب تغذية ثلاثية الطور بقاطع رئيسي {breaker} أمبير بناءً على حمل مقدّر {demand_kva:.0f} ك.ف.أ.",
                f"Request a three-phase supply rated {breaker} A at the main breaker for the {demand_kva:.0f} kVA diversified demand.",
                "high"),
        ]
        if transformer:
            recommendations.append(rec(
                f"الحمل يتجاوز ١٠٠ ك.ف.أ — نسّق مع الشركة السعودية للكهرباء على غرفة محول بمساحة ≈ {substation_area:.0f} م² بمدخل مستقل من الشارع. هذه الغرفة غير مدرجة في البرنامج المعماري الحالي.",
                f"The demand exceeds 100 kVA — coordinate a substation room of about {substation_area:.0f} m² with SEC, with independent street access. This room is not in the current architectural program.",
                "high"))
        recommendations.append(rec(
            "اعتمد إنارة LED بكثافة قدرة منخفضة مع تحكم بالمناطق لتقليل الحمل وأحمال التكييف الداخلية.",
            "Use LED lighting at a low power density with zone control to cut both the electrical load and the internal heat gain.",
            "medium"))
        recommendations.append(rec(
            "نفّذ نظام تأريض TN-S مع مساوي جهد رئيسي، واختبر المقاومة قبل التشغيل.",
            "Install a TN-S earthing system with main equipotential bonding, and test the resistance before energisation.",
            "high"))
        if brief["building_type"] in ("commercial", "mixed") or floors >= 4:
            recommendations.append(rec(
                "وفّر مصدرًا احتياطيًا لإنارة الطوارئ ومضخات الحريق والمصاعد مع لوحة طوارئ منفصلة.",
                "Provide standby supply for emergency lighting, fire pumps and lifts on a separate essential-services board.",
                "high"))
        recommendations.append(rec(
            "ادرس منظومة كهروضوئية على السطح — الإشعاع الشمسي المرتفع يجعل فترة الاسترداد قصيرة.",
            "Study a rooftop photovoltaic array — the high solar resource makes the payback period short.",
            "low"))

        return {
            "summary_ar": (
                f"حمل مركب {connected_kva:.0f} ك.ف.أ ومقدّر {demand_kva:.0f} ك.ف.أ، "
                f"قاطع رئيسي {breaker} أمبير، {'مع محول مخصص' if transformer else 'بدون محول مخصص'}."
            ),
            "summary_en": (
                f"{connected_kva:.0f} kVA connected and {demand_kva:.0f} kVA diversified, "
                f"main breaker {breaker} A, "
                f"{'with' if transformer else 'without'} a dedicated transformer."
            ),
            "metrics": metrics,
            "schedule": schedule,
            "load_blocks": blocks,
            "recommendations": recommendations,
            "assumptions": [
                note("مخصصات الأحمال بالفولت أمبير لكل متر مربع قيم تخطيطية لنوع المبنى.",
                     "The VA/m² allowances are planning figures for this building type."),
                note("معامل القدرة مفترض ٠٫٩ بعد تصحيح معامل القدرة.",
                     "A 0.9 power factor is assumed after correction."),
                note("حمل التكييف مأخوذ من مخرجات الوكيل الميكانيكي.",
                     "The HVAC load is taken from the mechanical agent's output."),
            ],
            "verify": [
                verify("حجم التغذية وموقع المحول واشتراطات التوصيل.",
                       "Service size, substation location and connection requirements.", "SEC"),
                verify("حسابات هبوط الجهد ومقاطع الكابلات وتنسيق الحماية.",
                       "Voltage drop, cable sizing and protection coordination.", "SBC 401"),
                verify("أنظمة إنذار الحريق وإنارة الطوارئ.",
                       "Fire alarm and emergency lighting systems.", "SBC 801 + Civil Defence"),
            ],
            "outputs": {
                "connected_kva": round(connected_kva, 1),
                "demand_kva": round(demand_kva, 1),
                "breaker_a": breaker,
                "transformer": transformer,
                "substation_area_m2": round(substation_area, 1),
                "boards": boards,
                "hvac_kw": round(hvac_kw, 1),
            },
        }
