"""Senior interior designer agent.

Works inside the architect's room schedule: sets clear ceiling heights
against the structural depth and the MEP void, writes a finishes schedule
suited to Saudi maintenance and climate realities, and checks accessibility
and acoustic separation.
"""

from app.agents.base import Agent, metric, note, rec, verify

# Finishes by space family: (floor, wall, ceiling) in Arabic and English.
FINISHES = {
    "majlis": {
        "ar": ("رخام أو بورسلين مقاس كبير", "دهان مع كسوة خشبية جزئية", "جبسبورد مع كورنيش وإنارة مخفية"),
        "en": ("Large-format porcelain or marble", "Paint with partial timber panelling", "Gypsum board with cove lighting"),
    },
    "living": {
        "ar": ("بورسلين مصقول", "دهان قابل للغسل", "جبسبورد مع إنارة موزعة"),
        "en": ("Polished porcelain", "Washable paint", "Gypsum board with distributed lighting"),
    },
    "bedroom": {
        "ar": ("بورسلين أو باركيه هندسي", "دهان مطفي", "جبسبورد مع إنارة محيطية"),
        "en": ("Porcelain or engineered timber", "Matt paint", "Gypsum board with perimeter lighting"),
    },
    "kitchen": {
        "ar": ("بورسلين مقاوم للانزلاق R10", "سيراميك حتى السقف خلف مناطق العمل", "جبسبورد مقاوم للرطوبة"),
        "en": ("Anti-slip porcelain R10", "Full-height ceramic behind work zones", "Moisture-resistant gypsum board"),
    },
    "bathroom": {
        "ar": ("بورسلين مقاوم للانزلاق R11 مع عزل مائي", "سيراميك حتى السقف مع عزل مائي", "جبسبورد مقاوم للرطوبة مع فتحة خدمة"),
        "en": ("Anti-slip porcelain R11 over tanking", "Full-height ceramic over tanking", "Moisture-resistant gypsum with access hatch"),
    },
    "circulation": {
        "ar": ("بورسلين مقاوم للتآكل", "دهان قابل للغسل مع حماية زوايا", "جبسبورد مع إنارة خطية"),
        "en": ("Hard-wearing porcelain", "Washable paint with corner guards", "Gypsum board with linear lighting"),
    },
    "retail": {
        "ar": ("بورسلين تقني عالي التحمل", "دهان أو ألواح قابلة للاستبدال", "سقف مشبك معدني قابل للفك"),
        "en": ("Heavy-duty technical porcelain", "Paint or demountable panels", "Accessible metal grid ceiling"),
    },
    "service": {
        "ar": ("دهان إيبوكسي أو بلاط صناعي", "دهان إيبوكسي", "مكشوف مع تنسيق الخدمات"),
        "en": ("Epoxy floor or industrial tile", "Epoxy paint", "Exposed with coordinated services"),
    },
}

# Which finish family each program keyword maps to.
SPACE_MAP = [
    (("مجلس", "majlis", "reception", "استقبال"), "majlis"),
    (("معيشة", "living", "dining", "طعام"), "living"),
    (("نوم", "bedroom"), "bedroom"),
    (("مطبخ", "kitchen"), "kitchen"),
    (("دورات", "bath", "toilet"), "bathroom"),
    (("لوبي", "lobby", "ممر", "corridor", "entrance", "مداخل"), "circulation"),
    (("تجاري", "retail", "تأجير", "lettable"), "retail"),
    (("خدمات", "service", "plant", "storage", "مخاز", "تخزين", "production", "إنتاج", "warehou", "مستودع", "offices", "مكاتب"), "service"),
]


def _family(ar, en):
    blob = (ar + " " + en).lower()
    for tokens, family in SPACE_MAP:
        if any(tok in blob for tok in tokens):
            return family
    return "living"


class InteriorAgent(Agent):
    agent_id = "interior"
    name_ar = "مصمم داخلي أول"
    name_en = "Senior Interior Designer"
    role_ar = "الارتفاعات الصافية، جدول التشطيبات، الإنارة، العزل الصوتي، إمكانية الوصول"
    role_en = "Clear heights, finishes schedule, lighting, acoustics, accessibility"
    depends_on = ("architecture", "structural", "mechanical")

    def analyse(self, brief, ctx):
        arch = ctx.get("architecture", {})
        struct = ctx.get("structural", {}).get("outputs", {})
        mech = ctx.get("mechanical", {}).get("outputs", {})

        floor_h = brief["floor_h"]
        slab_m = (struct.get("slab_mm") or 200) / 1000.0
        # Service void: duct depth plus insulation plus the ceiling board.
        duct_void = 0.35 if (mech.get("tons") or 0) > 12 else 0.25
        clear_h = floor_h - slab_m - duct_void

        units = brief["units"]
        party_walls = units > 1 or brief["building_type"] in ("apartment", "mixed")

        schedule = []
        for row in arch.get("schedule", []):
            family = _family(row.get("ar", ""), row.get("en", ""))
            fin = FINISHES[family]
            schedule.append({
                "ar": row.get("ar", ""),
                "en": row.get("en", ""),
                "area_m2": row.get("area_m2", 0),
                "floor_ar": fin["ar"][0], "floor_en": fin["en"][0],
                "wall_ar": fin["ar"][1], "wall_en": fin["en"][1],
                "ceiling_ar": fin["ar"][2], "ceiling_en": fin["en"][2],
            })

        wet_area = sum(r["area_m2"] for r in schedule
                       if _family(r["ar"], r["en"]) in ("bathroom", "kitchen"))

        metrics = [
            metric("ارتفاع الدور", "Floor-to-floor height", round(floor_h, 2), "m", "from the project record"),
            metric("سماكة البلاطة", "Slab depth", int(struct.get("slab_mm") or 200), "mm", "from the structural agent"),
            metric("فراغ الخدمات", "Service void", round(duct_void, 2), "m", "ducts, insulation and ceiling board"),
            metric("الارتفاع الصافي", "Clear ceiling height", round(clear_h, 2), "m", "floor-to-floor minus slab and void"),
            metric("مساحة المناطق الرطبة", "Wet area", round(wet_area, 1), "m²", "kitchens and bathrooms requiring tanking"),
            metric("عزل الجدران المشتركة", "Party wall rating", "STC 50+" if party_walls else "Not applicable", "",
                   "acoustic separation between units" if party_walls else "single occupancy"),
            metric("عرض الأبواب الصافي", "Clear door width", 900, "mm", "accessible route planning figure"),
            metric("دائرة دوران الكرسي المتحرك", "Wheelchair turning circle", 1500, "mm", "accessible route planning figure"),
        ]

        recommendations = []
        if clear_h < 2.70:
            recommendations.append(rec(
                f"الارتفاع الصافي {clear_h:.2f} م منخفض — ارفع ارتفاع الدور أو مرّر المجاري الرئيسية في الممرات فقط بسقف منخفض موضعي.",
                f"A {clear_h:.2f} m clear height is tight — raise the floor-to-floor height, or route the main ducts over corridors only with a local bulkhead.",
                "high"))
        else:
            recommendations.append(rec(
                f"الارتفاع الصافي {clear_h:.2f} م مناسب — ثبّت مستوى السقف مبكرًا مع الميكانيكا قبل تفصيل الجبس.",
                f"The {clear_h:.2f} m clear height works — fix the ceiling level with mechanical early, before detailing the gypsum.",
                "medium"))
        recommendations.append(rec(
            "اعتمد عزلًا مائيًا كاملًا في الحمامات والمطابخ مع رفع العزل ٣٠ سم على الجدران واختبار غمر قبل التبليط.",
            "Tank bathrooms and kitchens fully, turn the membrane 300 mm up the walls, and flood-test before tiling.",
            "high"))
        if party_walls:
            recommendations.append(rec(
                "الجدران المشتركة بين الوحدات تحتاج عزلًا صوتيًا لا يقل عن STC 50 مع فصل عند البلاطة لمنع انتقال الصوت.",
                "Party walls between units need at least STC 50 with a break at the slab to stop flanking transmission.",
                "high"))
        recommendations.append(rec(
            "اختر مواد تتحمل الغبار والحرارة وسهلة التنظيف — البورسلين التقني والدهانات القابلة للغسل تقلل الصيانة.",
            "Choose materials that tolerate dust and heat and clean easily — technical porcelain and washable paints cut maintenance.",
            "medium"))
        recommendations.append(rec(
            "استخدم درجة حرارة لون ٣٠٠٠ كلفن في المجالس والنوم و٤٠٠٠ كلفن في المطابخ والخدمات، مع معامل تجانس لوني CRI 80 فأعلى.",
            "Use 3000 K in majlis and bedrooms and 4000 K in kitchens and services, at CRI 80 or better.",
            "low"))
        recommendations.append(rec(
            "افصل مدخل ومسار مجلس الرجال عن المسار العائلي بصريًا، مع دورة مياه ضيوف قريبة من المدخل.",
            "Separate the men's majlis entry and route visually from the family circulation, with a guest WC near the entrance.",
            "medium"))

        return {
            "summary_ar": (
                f"ارتفاع صافٍ {clear_h:.2f} م بعد بلاطة {int(struct.get('slab_mm') or 200)} مم "
                f"وفراغ خدمات {duct_void:.2f} م، وجدول تشطيبات لـ{len(schedule)} فراغًا."
            ),
            "summary_en": (
                f"A {clear_h:.2f} m clear height after a {int(struct.get('slab_mm') or 200)} mm slab and a "
                f"{duct_void:.2f} m service void, with a finishes schedule across {len(schedule)} spaces."
            ),
            "metrics": metrics,
            "schedule": schedule,
            "recommendations": recommendations,
            "assumptions": [
                note("فراغ الخدمات مقدّر من حجم منظومة التكييف ولم يُنسّق على مسارات فعلية.",
                     "The service void is estimated from the HVAC system size, not coordinated against real duct routes."),
                note("التشطيبات مقترحات نوعية وليست مواصفات فنية أو أسماء تجارية.",
                     "Finishes are generic proposals, not technical specifications or brand selections."),
            ],
            "verify": [
                verify("الارتفاعات الصافية بعد تنسيق المسارات الفعلية للخدمات.",
                       "Clear heights after coordinating the real service routes.", "Coordinated services drawings"),
                verify("متطلبات إمكانية الوصول ومقاومة الحريق لمواد التشطيب.",
                       "Accessibility requirements and the fire rating of finish materials.", "SBC 201 + SBC 801"),
                verify("أداء العزل الصوتي المطلوب بين الوحدات.",
                       "Required acoustic performance between units.", "SBC 201"),
            ],
            "outputs": {
                "clear_height_m": round(clear_h, 2),
                "service_void_m": round(duct_void, 2),
                "wet_area_m2": round(wet_area, 1),
                "party_walls": party_walls,
                "spaces": len(schedule),
            },
        }
