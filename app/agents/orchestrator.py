"""Coordinates the seven senior agents into one design package.

Agents run in dependency order and each one reads the packages produced
before it, so the structural engineer sizes against the architect's
envelope and the electrical engineer sizes against the mechanical
engineer's cooling load.

The part that makes this a team rather than seven calculators is
`coordinate()`: it compares the finished packages against each other and
reports the clashes a lead engineer would catch in a coordination meeting
— the ones where each discipline is individually right and the building
still does not work.
"""

from app.agents.architecture import ArchitectureAgent
from app.agents.base import build_brief, package_envelope
from app.agents.electrical import ElectricalAgent
from app.agents.interior import InteriorAgent
from app.agents.mechanical import MechanicalAgent
from app.agents.quantity import QuantityAgent
from app.agents.regulation import RegulationAgent
from app.agents.structural import StructuralAgent

# Dependency order. Each agent only reads packages produced before it.
AGENTS = (
    ArchitectureAgent(),
    StructuralAgent(),
    MechanicalAgent(),
    ElectricalAgent(),
    InteriorAgent(),
    QuantityAgent(),
    RegulationAgent(),
)

AGENT_INDEX = {agent.agent_id: agent for agent in AGENTS}

MIN_CLEAR_HEIGHT = 2.70  # m, the height below which a residential room feels low


def _issue(issue_id, severity, disciplines, ar, en, action_ar, action_en):
    return {
        "id": issue_id,
        "severity": severity,
        "disciplines": list(disciplines),
        "ar": ar,
        "en": en,
        "action_ar": action_ar,
        "action_en": action_en,
    }


def coordinate(brief: dict, packages: dict) -> list:
    """Cross-discipline clash checks across the finished packages."""
    issues = []
    arch = packages.get("architecture", {}).get("outputs", {})
    struct = packages.get("structural", {}).get("outputs", {})
    mech = packages.get("mechanical", {}).get("outputs", {})
    elec = packages.get("electrical", {}).get("outputs", {})
    inter = packages.get("interior", {}).get("outputs", {})

    # 1. Floor-to-floor height against slab depth plus the service void.
    clear_h = inter.get("clear_height_m")
    if clear_h is not None and clear_h < MIN_CLEAR_HEIGHT:
        needed = brief["floor_h"] + (MIN_CLEAR_HEIGHT - clear_h)
        issues.append(_issue(
            "clear-height", "high", ["structural", "mechanical", "interior"],
            f"الارتفاع الصافي {clear_h:.2f} م أقل من {MIN_CLEAR_HEIGHT:.2f} م بعد بلاطة "
            f"{struct.get('slab_mm')} مم وفراغ خدمات {inter.get('service_void_m')} م.",
            f"Clear height of {clear_h:.2f} m falls below {MIN_CLEAR_HEIGHT:.2f} m once the "
            f"{struct.get('slab_mm')} mm slab and the {inter.get('service_void_m')} m service void are taken out.",
            f"ارفع ارتفاع الدور إلى {needed:.2f} م، أو قلّل عمق المجاري، أو اعتمد بلاطة أنحف ببحر أقصر.",
            f"Raise the floor-to-floor height to {needed:.2f} m, reduce the duct depth, or shorten the span for a thinner slab."))

    # 2. A substation the architectural program has no room for.
    if elec.get("transformer") and elec.get("substation_area_m2", 0) > 0:
        issues.append(_issue(
            "substation-room", "high", ["architecture", "electrical"],
            f"الحمل الكهربائي {elec.get('demand_kva')} ك.ف.أ يستلزم غرفة محول "
            f"{elec.get('substation_area_m2')} م² غير موجودة في البرنامج المعماري.",
            f"The {elec.get('demand_kva')} kVA demand requires a {elec.get('substation_area_m2')} m² "
            f"substation room that does not exist in the architectural program.",
            "خصّص الغرفة على حد الأرض بمدخل مستقل من الشارع قبل تثبيت المخطط الأرضي.",
            "Allocate the room on the plot boundary with independent street access before the ground floor plan is fixed."))

    # 3. Roof area against outdoor units, tanks and access.
    roof_area = brief["footprint"]
    roof_demand = mech.get("outdoor_area_m2", 0) + (mech.get("roof_tank_m3", 0) * 1.5)
    if roof_area and roof_demand > roof_area * 0.55:
        issues.append(_issue(
            "roof-congestion", "medium", ["architecture", "mechanical"],
            f"معدات السطح تحتاج ≈ {roof_demand:.0f} م² من أصل {roof_area:.0f} م² "
            f"({roof_demand / roof_area * 100:.0f}٪ من مساحة السطح).",
            f"Roof plant needs about {roof_demand:.0f} m² of the {roof_area:.0f} m² roof "
            f"({roof_demand / roof_area * 100:.0f}% of the area).",
            "ادرس بدائل: مبردات مركزية أقل مساحة، أو نقل الخزانات إلى الأرضي مع مضخات ضغط.",
            "Consider a more compact central plant, or move the tanks to ground level with booster pumps."))

    # 4. Roof tank as a structural point load.
    tank = mech.get("roof_tank_m3", 0)
    if tank > 0:
        tank_load = tank * 10.0  # kN, water plus tank
        issues.append(_issue(
            "roof-tank-load", "medium", ["structural", "mechanical"],
            f"خزان السطح {tank:.1f} م³ يضيف حملًا موضعيًا ≈ {tank_load:.0f} ك.ن لم يدخل في تحليل البلاطة.",
            f"The {tank:.1f} m³ roof tank adds a point load of about {tank_load:.0f} kN that the slab takedown did not include.",
            "ثبّت موقع الخزان فوق عمود أو جدار حامل، وأعد فحص البلاطة موضعيًا.",
            "Locate the tank over a column or bearing wall, and re-check the slab locally."))

    # 5. Parking demand against the open site area left after the footprint.
    required_bays = max(brief["units"], brief["parking"])
    # 2.50 x 5.00 m bay plus aisle and manoeuvring: ~25 m2 per bay in a yard.
    parking_area = required_bays * 25.0
    open_site = max(0.0, brief["plot_area"] - brief["footprint"])
    if parking_area > open_site:
        issues.append(_issue(
            "parking-area", "high", ["architecture", "regulation"],
            f"{required_bays} موقفًا تحتاج ≈ {parking_area:.0f} م² بينما المتاح خارج البصمة {open_site:.0f} م².",
            f"{required_bays} bays need about {parking_area:.0f} m² but only {open_site:.0f} m² remains outside the footprint.",
            "قلّص البصمة، أو انقل المواقف إلى قبو أو مظلات، أو راجع اشتراط المواقف لدى الأمانة.",
            "Reduce the footprint, move parking to a basement or covered bays, or review the municipal parking requirement."))

    # 6. Fire reserve stacked on top of domestic storage.
    if mech.get("sprinklers") and mech.get("fire_reserve_m3", 0) > 0:
        total_storage = mech.get("ground_tank_m3", 0) + mech.get("fire_reserve_m3", 0)
        issues.append(_issue(
            "fire-reserve", "high", ["mechanical", "structural", "regulation"],
            f"إجمالي التخزين {total_storage:.0f} م³ بعد إضافة احتياطي الحريق "
            f"{mech.get('fire_reserve_m3'):.0f} م³ — يحتاج خزانًا أرضيًا أكبر وحفرًا إضافيًا.",
            f"Total storage reaches {total_storage:.0f} m³ once the {mech.get('fire_reserve_m3'):.0f} m³ fire reserve "
            f"is added — this needs a larger ground tank and extra excavation.",
            "افصل احتياطي الحريق بحاجز داخلي يمنع سحبه للاستخدام اليومي، وأدرج الحفر في التكلفة.",
            "Separate the fire reserve with an internal baffle so daily demand cannot draw it down, and carry the excavation in the cost."))

    # 7. Plant and service rooms against the architect's circulation budget.
    services_needed = mech.get("plant_area_m2", 0) + elec.get("substation_area_m2", 0) + arch.get("core_area_m2", 0)
    circulation_budget = brief["gfa"] - (arch.get("net_area_m2") or brief["gfa"])
    if circulation_budget and services_needed > circulation_budget:
        issues.append(_issue(
            "services-budget", "medium", ["architecture", "mechanical", "electrical"],
            f"غرف الخدمات والنواة تحتاج ≈ {services_needed:.0f} م² بينما ميزانية الحركة والخدمات "
            f"{circulation_budget:.0f} م² — المساحة الصافية ستنخفض.",
            f"Plant rooms and the core need about {services_needed:.0f} m² against a circulation and services "
            f"budget of {circulation_budget:.0f} m² — the net area will drop.",
            "أعد توزيع البرنامج أو ارفع نسبة الحركة، وحدّث المساحات الصافية والتكلفة بناءً عليها.",
            "Re-balance the program or raise the circulation allowance, then update the net areas and the cost."))

    # 8. Structural exposure that the cost plan was not told about.
    if struct.get("exposure") == "coastal":
        issues.append(_issue(
            "coastal-cost", "medium", ["structural", "quantity"],
            "الموقع ساحلي ويستلزم رتبة خرسانة أعلى وغطاء أكبر وأسمنتًا مقاومًا للكبريتات — أعلى من نطاق الأسعار القياسي.",
            "The coastal exposure calls for a higher concrete grade, deeper cover and sulfate-resisting cement — above the standard rate band.",
            "استخدم الحد الأعلى لنطاق أسعار الخرسانة والأساسات في خطة التكلفة.",
            "Price the concrete and substructure elements at the top of their rate bands in the cost plan."))

    # 9. A raft the substructure rate band may not cover.
    if struct.get("raft"):
        issues.append(_issue(
            "raft-cost", "low", ["structural", "quantity"],
            "اعتماد اللبشة يرفع كمية الخرسانة والحفر عن افتراض القواعد المنفصلة في نطاق أسعار الأساسات.",
            "Adopting a raft raises the concrete and excavation quantities above the pad-footing assumption in the substructure rate band.",
            "راجع بند الأساسات في خطة التكلفة بعد تثبيت نوع الأساس من تقرير التربة.",
            "Revisit the substructure element once the soil report fixes the foundation type."))

    return issues


def run_design(params: dict) -> dict:
    """Run all seven agents over a project record and coordinate the result."""
    brief = build_brief(params)
    packages = {}
    ordered = []
    for agent in AGENTS:
        package = agent.run(brief, packages)
        packages[agent.agent_id] = package
        ordered.append(package)

    issues = coordinate(brief, packages)
    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for issue in issues:
        severity_counts[issue["severity"]] = severity_counts.get(issue["severity"], 0) + 1

    regulation = packages.get("regulation", {}).get("outputs", {})
    quantity = packages.get("quantity", {}).get("outputs", {})

    return package_envelope("alarrab_design_package", {
        "brief": brief,
        "agents": ordered,
        "coordination": {
            "issues": issues,
            "counts": severity_counts,
            "total": len(issues),
        },
        "headline": {
            "gfa_m2": round(brief["gfa"], 1),
            "floors": brief["floors"],
            "preliminary_score": regulation.get("score", 0),
            "cost_low_sar": quantity.get("net_low", 0),
            "cost_high_sar": quantity.get("net_high", 0),
            "months": quantity.get("months", 0),
            "coordination_issues": len(issues),
            "verification_items": regulation.get("register_items", 0),
        },
    })


def list_agents() -> dict:
    """Roster of the agents without running them."""
    return package_envelope("alarrab_agent_roster", {
        "agents": [
            {
                "agent_id": agent.agent_id,
                "name_ar": agent.name_ar,
                "name_en": agent.name_en,
                "role_ar": agent.role_ar,
                "role_en": agent.role_en,
                "depends_on": list(agent.depends_on),
                "seniority": "senior",
            }
            for agent in AGENTS
        ],
        "count": len(AGENTS),
    })
