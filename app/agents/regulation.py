"""Senior regulation review specialist agent.

Runs last. Reuses the existing draft-rule assessment engine rather than
restating the checks, maps each discipline onto the code part and the
authority that governs it, and consolidates every other agent's
verification register into one list the team has to clear.

This agent is the one that enforces the governance invariants: it reports
what still has to be proven, and it never certifies anything.
"""

from app.agents.base import Agent, metric, note, rec, verify
from app.engine.assessment import evaluate

# Discipline -> (code part, authority). The code parts are the ordinary
# governing references; the exact clause always comes from the official
# published document, never from this mapping.
GOVERNANCE_MAP = [
    ("architecture", "معماري", "Architecture", "SBC 201 / SBC 1101",
     "الأمانة أو البلدية عبر منصة بلدي", "Municipality via the Balady platform"),
    ("structural", "إنشائي", "Structural", "SBC 301 / 302 / 303 / 304",
     "مكتب هندسي مرخص + الأمانة", "Licensed engineering office + municipality"),
    ("electrical", "كهربائي", "Electrical", "SBC 401",
     "الشركة السعودية للكهرباء", "Saudi Electricity Company"),
    ("mechanical", "ميكانيكي", "Mechanical", "SBC 501 / 701",
     "شركة المياه الوطنية + الدفاع المدني", "National Water Company + Civil Defence"),
    ("interior", "داخلي", "Interior", "SBC 201 + SBC 801",
     "الأمانة + الدفاع المدني", "Municipality + Civil Defence"),
    ("quantity", "كميات", "Quantity surveying", "—",
     "لا تخضع لاعتماد نظامي", "Not subject to regulatory approval"),
    ("fire", "حريق", "Fire safety", "SBC 801",
     "الدفاع المدني", "Civil Defence"),
]

# Approval steps in the order an applicant normally meets them.
APPROVAL_STEPS = [
    ("رخصة البناء", "Building permit", "بلدي / الأمانة", "Balady / municipality"),
    ("الاعتماد الإنشائي من مكتب مرخص", "Structural sign-off by a licensed office", "الهيئة السعودية للمهندسين", "Saudi Council of Engineers"),
    ("اعتماد الدفاع المدني لمتطلبات السلامة", "Civil Defence safety approval", "الدفاع المدني", "Civil Defence"),
    ("توصيل الكهرباء", "Electricity connection", "الشركة السعودية للكهرباء", "Saudi Electricity Company"),
    ("توصيل المياه والصرف", "Water and drainage connection", "شركة المياه الوطنية", "National Water Company"),
    ("شهادة الإشغال", "Occupancy certificate", "بلدي / الأمانة", "Balady / municipality"),
]


class RegulationAgent(Agent):
    agent_id = "regulation"
    name_ar = "أخصائي مراجعة نظامية أول"
    name_en = "Senior Regulation Review Specialist"
    role_ar = "فحص القواعد المسودة، مصفوفة الجهات، سجل التحقق، ضوابط الحوكمة"
    role_en = "Draft rule checks, authority matrix, verification register, governance controls"
    depends_on = ("architecture", "structural", "electrical", "mechanical", "interior", "quantity")

    def analyse(self, brief, ctx):
        mech = ctx.get("mechanical", {}).get("outputs", {})
        elec = ctx.get("electrical", {}).get("outputs", {})

        # Reuse the existing engine so the draft rules live in one place.
        assessment = evaluate({
            "project_name": brief["project_name"],
            "city": brief["city"],
            "land_use": brief["land_use"],
            "plot_area_m2": brief["plot_area"],
            "floors": brief["floors"],
            "building_height_m": brief["height"],
            "setback_front_m": brief["sb_f"],
            "setback_side_m": brief["sb_s"],
            "setback_rear_m": brief["sb_r"],
            "coverage_ratio": brief["coverage"],
            "far": brief["far"],
            "parking_spaces": brief["parking"],
            "units": brief["units"],
        })

        counts = assessment["counts"]
        failures = [f for f in assessment["findings"] if f["status"] == "fail"]

        governance = []
        for agent_id, ar, en, code_part, auth_ar, auth_en in GOVERNANCE_MAP:
            governance.append({
                "agent_id": agent_id,
                "discipline_ar": ar,
                "discipline_en": en,
                "code_part": code_part,
                "authority_ar": auth_ar,
                "authority_en": auth_en,
            })

        approvals = []
        for ar, en, body_ar, body_en in APPROVAL_STEPS:
            approvals.append({
                "ar": ar, "en": en, "authority_ar": body_ar, "authority_en": body_en,
                "status_ar": "مطلوب", "status_en": "Required",
            })
        if mech.get("sprinklers"):
            approvals.insert(3, {
                "ar": "اعتماد مخطط شبكة الرشاشات",
                "en": "Sprinkler layout approval",
                "authority_ar": "الدفاع المدني", "authority_en": "Civil Defence",
                "status_ar": "مطلوب", "status_en": "Required",
            })
        if elec.get("transformer"):
            approvals.insert(4, {
                "ar": "اعتماد موقع غرفة المحول",
                "en": "Substation room location approval",
                "authority_ar": "الشركة السعودية للكهرباء", "authority_en": "Saudi Electricity Company",
                "status_ar": "مطلوب", "status_en": "Required",
            })

        # Consolidate every agent's verification register.
        register = []
        for agent_id, package in ctx.items():
            for item in package.get("verify", []):
                register.append({
                    "agent_id": agent_id,
                    "ar": item.get("ar", ""),
                    "en": item.get("en", ""),
                    "source": item.get("source", ""),
                })

        metrics = [
            metric("النتيجة الأولية", "Preliminary score", assessment["score"], "/100", "draft rule set, severity weighted"),
            metric("فحوصات مستوفاة", "Checks passed", counts["pass"], "", "draft rules only"),
            metric("فحوصات غير مستوفاة", "Checks failed", counts["fail"], "", "draft rules only"),
            metric("فحوصات تحتاج مراجعة", "Checks needing review", counts["needs_review"], "", "missing or unclear input"),
            metric("بنود سجل التحقق", "Verification register items", len(register), "", "raised across all disciplines"),
            metric("اعتمادات الجهات المطلوبة", "Authority approvals required", len(approvals), "", "typical permit path"),
            metric("قواعد رسمية مستخدمة", "Official rules applied", 0, "", "the shipped rule set is draft by design"),
        ]

        recommendations = []
        for finding in failures:
            recommendations.append(rec(
                f"مخالفة مسودة: {finding['title_ar']} — {finding['detail']}",
                f"Draft check failed: {finding['title_en']} — {finding['detail']}",
                "high" if finding["severity"] == "high" else "medium"))
        recommendations.append(rec(
            "لا تُقدَّم أي مخرجات من هذا النظام إلى جهة حكومية قبل اعتمادها من مكتب هندسي مرخص.",
            "No output from this system may be submitted to any authority before a licensed engineering office signs it off.",
            "high"))
        recommendations.append(rec(
            "تحقق من اشتراطات النطاق العمراني للقطعة تحديدًا عبر منصة بلدي — الحدود تختلف بين الأمانات وبين المخططات.",
            "Check this specific plot's zoning on the Balady platform — limits vary between municipalities and between subdivisions.",
            "high"))
        if mech.get("sprinklers") or brief["floors"] >= 4:
            recommendations.append(rec(
                "أشرك الدفاع المدني مبكرًا — متطلبات السلامة تعيد تشكيل المخارج والنواة والخزانات إذا تأخرت.",
                "Engage Civil Defence early — safety requirements reshape exits, the core and the tanks if they arrive late.",
                "high"))

        return {
            "summary_ar": (
                f"نتيجة أولية {assessment['score']}/١٠٠ على قواعد مسودة: {counts['pass']} مستوفى و{counts['fail']} غير مستوفى، "
                f"مع {len(register)} بندًا في سجل التحقق و{len(approvals)} اعتمادًا مطلوبًا."
            ),
            "summary_en": (
                f"A preliminary {assessment['score']}/100 on draft rules: {counts['pass']} passed and {counts['fail']} failed, "
                f"with {len(register)} verification items and {len(approvals)} authority approvals required."
            ),
            "metrics": metrics,
            "schedule": governance,
            "assessment": assessment,
            "approvals": approvals,
            "register": register,
            "recommendations": recommendations,
            "assumptions": [
                note("الفحوصات تستخدم مجموعة القواعد المسودة المرفقة بالنظام وليست بنود الكود الرسمية.",
                     "Checks use the draft rule set shipped with the system, not official code clauses."),
                note("مصفوفة الجهات إرشادية وقد تختلف حسب الأمانة ونوع النشاط.",
                     "The authority matrix is indicative and varies by municipality and activity type."),
            ],
            "verify": [
                verify("كل قيمة نظامية مقابل الوثيقة الرسمية المنشورة وبند محدد.",
                       "Every regulatory value against the official published document and a specific clause.",
                       "sbc.gov.sa"),
                verify("اشتراطات القطعة ونوع النشاط لدى الأمانة المختصة.",
                       "Plot and activity requirements with the relevant municipality.", "Balady"),
            ],
            "outputs": {
                "score": assessment["score"],
                "counts": counts,
                "failures": len(failures),
                "register_items": len(register),
                "approvals": len(approvals),
                "official_rules_applied": 0,
            },
        }
