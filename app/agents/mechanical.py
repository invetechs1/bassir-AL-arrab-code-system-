"""Senior mechanical engineer agent (HVAC, plumbing, fire protection).

Cooling dominates in the Saudi climate, so the cooling load drives the
system selection, the plant space and — through the electrical agent —
the building's electrical service. Also sizes domestic water storage,
fresh air and the fire protection scope.
"""

from app.agents.base import Agent, metric, note, rec, verify

# Indicative cooling density: m2 of floor area per ton of refrigeration.
# A lower number means a heavier load. Concept-stage figures only; a real
# design needs a room-by-room load calculation.
M2_PER_TR = {
    "villa": 20.0,
    "apartment": 21.0,
    "commercial": 16.0,
    "mixed": 18.0,
    "industrial": 28.0,
}

# Indicative domestic water demand, litres per person per day.
WATER_LPD = {
    "villa": 300.0,
    "apartment": 250.0,
    "commercial": 60.0,
    "mixed": 180.0,
    "industrial": 80.0,
}

# Indicative outdoor air, litres/second per person.
FRESH_AIR_LPS = {
    "villa": 7.5,
    "apartment": 7.5,
    "commercial": 10.0,
    "mixed": 8.5,
    "industrial": 12.0,
}

# Peak summer design dry-bulb by region, for context in the narrative.
DESIGN_TEMP = {
    "الرياض": 46, "riyadh": 46, "جدة": 42, "jeddah": 42, "مكة": 47, "makkah": 47,
    "الدمام": 45, "dammam": 45, "المدينة": 44, "madinah": 44, "أبها": 32, "abha": 32,
    "تبوك": 42, "tabuk": 42, "حائل": 43, "hail": 43,
}


def _design_temp(city):
    low = (city or "").strip().lower()
    for token, temp in DESIGN_TEMP.items():
        if token in low:
            return temp
    return 45


class MechanicalAgent(Agent):
    agent_id = "mechanical"
    name_ar = "مهندس ميكانيكي أول"
    name_en = "Senior Mechanical Engineer"
    role_ar = "أحمال التكييف، اختيار المنظومة، التهوية، السباكة، مكافحة الحريق"
    role_en = "Cooling load, system selection, ventilation, plumbing, fire protection"
    depends_on = ("architecture",)

    def analyse(self, brief, ctx):
        gfa = brief["gfa"]
        btype = brief["building_type"]
        floors = brief["floors"]
        arch = ctx.get("architecture", {}).get("outputs", {})
        occupants = arch.get("occupants") or max(1, int(gfa / 30))

        design_temp = _design_temp(brief["city"])
        m2_per_tr = M2_PER_TR.get(btype, 20.0)
        # Hotter inland sites carry a heavier envelope gain.
        if design_temp >= 46:
            m2_per_tr *= 0.92
        tons = gfa / m2_per_tr
        cooling_kw = tons * 3.517

        if tons <= 12:
            sys_ar, sys_en = "وحدات منفصلة (سبليت) موزعة", "Distributed split units"
        elif tons <= 60:
            sys_ar, sys_en = "منظومة تدفق مبرد متغير VRF", "VRF system"
        elif tons <= 120:
            sys_ar, sys_en = "وحدات مناولة هواء مع مكثفات هوائية", "Ducted units with air-cooled condensers"
        else:
            sys_ar, sys_en = "مبردات مياه مركزية (تشيلر)", "Central water-cooled chiller plant"

        fresh_air = occupants * FRESH_AIR_LPS.get(btype, 7.5)

        daily_water = occupants * WATER_LPD.get(btype, 250.0)
        # Ground tank at one day of storage, roof tank at a third of a day.
        ground_tank_m3 = daily_water / 1000.0
        roof_tank_m3 = max(1.0, daily_water / 3000.0)

        # Fire protection scope. These are the ordinary triggers a designer
        # expects; the binding trigger is Civil Defence's review of SBC 801.
        height = brief["height"]
        sprinklers = height > 15 or gfa > 1500 or btype in ("commercial", "mixed", "industrial")
        standpipe = height > 15 or floors >= 4
        fire_reserve_m3 = 0.0
        if sprinklers:
            # Light hazard: ~1900 L/min for 30 min is a common planning reserve.
            fire_reserve_m3 = 57.0 if btype in ("commercial", "mixed", "industrial") else 30.0

        # Plant space and riser allowance.
        plant_area = max(6.0, gfa * 0.02)
        # Condenser/outdoor unit area on the roof, ~0.9 m2 per TR with access.
        outdoor_area = tons * 0.9

        metrics = [
            metric("حرارة التصميم الصيفية", "Summer design temperature", design_temp, "°C",
                   f"regional indicative value for {brief['city'] or 'the site'}"),
            metric("حمل التبريد", "Cooling load", round(tons, 1), "TR",
                   f"indicative {m2_per_tr:.1f} m²/TR for this occupancy"),
            metric("حمل التبريد", "Cooling load", round(cooling_kw, 1), "kW", "1 TR = 3.517 kW"),
            metric("المنظومة المقترحة", "Proposed system", sys_en, "", f"selected at {tons:.0f} TR"),
            metric("الهواء النقي", "Outdoor air", round(fresh_air), "L/s",
                   f"{FRESH_AIR_LPS.get(btype, 7.5):g} L/s per person for {occupants} people"),
            metric("استهلاك المياه اليومي", "Daily water demand", round(daily_water), "L/day",
                   f"{WATER_LPD.get(btype, 250):g} L/person/day"),
            metric("خزان أرضي", "Ground tank", round(ground_tank_m3, 1), "m³", "one day of storage"),
            metric("خزان علوي", "Roof tank", round(roof_tank_m3, 1), "m³", "one third of a day"),
            metric("رشاشات الحريق", "Sprinkler system", "Required" if sprinklers else "Not triggered", "",
                   "planning trigger on height, area and occupancy"),
            metric("شبكة الفوهات الرطبة", "Wet standpipe", "Required" if standpipe else "Not triggered", "",
                   "planning trigger on height and storey count"),
            metric("احتياطي مياه الحريق", "Fire water reserve", round(fire_reserve_m3, 1), "m³",
                   "indicative light-hazard reserve" if sprinklers else "no sprinkler trigger"),
            metric("مساحة غرف الخدمات الفنية", "Plant room area", round(plant_area, 1), "m²", "~2% of gross floor area"),
            metric("مساحة الوحدات الخارجية", "Outdoor unit area", round(outdoor_area, 1), "m²",
                   "~0.9 m²/TR including service access"),
        ]

        recommendations = [
            rec(f"اعتمد {sys_ar} لحمل {tons:.0f} طن تبريد.",
                f"Adopt {sys_en.lower()} for the {tons:.0f} TR load.", "high"),
            rec(f"احجز {outdoor_area:.0f} م² على السطح للوحدات الخارجية مع ممرات خدمة ٠٫٩ م بين الصفوف.",
                f"Reserve {outdoor_area:.0f} m² of roof for outdoor units with 0.9 m service aisles between rows.", "high"),
            rec("اعزل السطح والجدران الخارجية بما يحقق متطلبات ترشيد الطاقة — العزل أرخص من سعة تبريد إضافية.",
                "Insulate the roof and external walls to meet the energy conservation requirements — insulation is cheaper than extra cooling capacity.", "high"),
        ]
        if sprinklers:
            recommendations.append(rec(
                f"المبنى يستوجب شبكة رشاشات — أضف {fire_reserve_m3:.0f} م³ احتياطي حريق مخصص لا يُسحب منه للاستخدام اليومي، واعتمد المخطط من الدفاع المدني.",
                f"The building triggers a sprinkler system — add a dedicated {fire_reserve_m3:.0f} m³ fire reserve that daily demand cannot draw down, and have the layout approved by Civil Defence.",
                "high"))
        if roof_tank_m3 > 0:
            recommendations.append(rec(
                f"خزان السطح {roof_tank_m3:.1f} م³ يضيف حملًا موضعيًا ≈ {roof_tank_m3 * 10:.0f} ك.ن — بلّغ المهندس الإنشائي بموقعه.",
                f"The {roof_tank_m3:.1f} m³ roof tank adds a point load of about {roof_tank_m3 * 10:.0f} kN — pass its location to the structural engineer.",
                "high"))
        recommendations.append(rec(
            "افصل عدادات المياه لكل وحدة، ووفّر تصريفًا للمكثفات إلى شبكة الصرف لا إلى الواجهات.",
            "Meter water per unit, and drain condensate to the drainage network rather than onto facades.", "medium"))

        return {
            "summary_ar": (
                f"حمل تبريد {tons:.0f} طن ({cooling_kw:.0f} ك.و) عبر {sys_ar}، "
                f"وتخزين مياه {ground_tank_m3:.1f} م³ أرضي و{roof_tank_m3:.1f} م³ علوي."
            ),
            "summary_en": (
                f"A {tons:.0f} TR ({cooling_kw:.0f} kW) cooling load served by {sys_en.lower()}, "
                f"with {ground_tank_m3:.1f} m³ ground and {roof_tank_m3:.1f} m³ roof water storage."
            ),
            "metrics": metrics,
            "schedule": [],
            "recommendations": recommendations,
            "assumptions": [
                note("حمل التبريد مقدّر بقاعدة م²/طن ولم يُحسب غرفة بغرفة.",
                     "The cooling load uses an m²/TR rule of thumb, not a room-by-room calculation."),
                note("المبنى مفترض جيد العزل بنوافذ مزدوجة.",
                     "The building is assumed to be well insulated with double glazing."),
                note("التخزين مبني على يوم واحد من الاستهلاك دون انقطاع مطوّل.",
                     "Storage assumes one day of demand with no extended supply interruption."),
            ],
            "verify": [
                verify("حساب أحمال التبريد التفصيلي ومعدلات التهوية.",
                       "Detailed cooling load calculation and ventilation rates.", "SBC 501 + ASHRAE"),
                verify("متطلبات مكافحة الحريق واحتياطي المياه واعتماد الدفاع المدني.",
                       "Fire protection scope, water reserve and Civil Defence approval.", "SBC 801 + Civil Defence"),
                verify("اشتراطات التوصيل ومعدلات الاستهلاك لدى شركة المياه الوطنية.",
                       "Connection requirements and demand rates with the water utility.", "NWC"),
            ],
            "outputs": {
                "tons": round(tons, 1),
                "cooling_kw": round(cooling_kw, 1),
                "system_en": sys_en,
                "system_ar": sys_ar,
                "ground_tank_m3": round(ground_tank_m3, 1),
                "roof_tank_m3": round(roof_tank_m3, 1),
                "fire_reserve_m3": round(fire_reserve_m3, 1),
                "sprinklers": sprinklers,
                "standpipe": standpipe,
                "plant_area_m2": round(plant_area, 1),
                "outdoor_area_m2": round(outdoor_area, 1),
                "daily_water_l": round(daily_water),
            },
        }
