"""Senior quantity surveyor agent.

Takes off approximate quantities from the geometry the other agents fixed,
prices them into an elemental cost plan, and spreads the result over a
construction programme.

Every rate here is an indicative planning BAND, not a quotation. Rates move
with market conditions, location, specification and procurement route, so
the agent reports a low-high range for each element and never a single
price. Nothing in this output may be used for a tender, a contract sum or
a client commitment without a priced bill from the market.
"""

from app.agents.base import Agent, metric, note, rec, rng, verify

# Indicative rate bands (SAR), low-high. Planning figures for order-of-magnitude
# budgeting only; they are not quotations and carry no market validity date.
RATES = {
    "substructure":   {"unit": "m² footprint", "low": 450,  "high": 750},
    "frame_slabs":    {"unit": "m² GFA",       "low": 600,  "high": 950},
    "blockwork":      {"unit": "m² wall",      "low": 110,  "high": 180},
    "external_finish":{"unit": "m² facade",    "low": 180,  "high": 420},
    "internal_finish":{"unit": "m² GFA",       "low": 350,  "high": 750},
    "joinery_doors":  {"unit": "m² GFA",       "low": 90,   "high": 200},
    "mep_mech":       {"unit": "m² GFA",       "low": 280,  "high": 520},
    "mep_elec":       {"unit": "m² GFA",       "low": 200,  "high": 380},
    "external_works": {"unit": "m² open site", "low": 150,  "high": 320},
}

PRELIMS_PCT = 0.10
CONTINGENCY_PCT = 0.10
DESIGN_FEES_PCT = 0.06
VAT_PCT = 0.15

# Indicative construction rate, m2 of gross floor area per month.
BUILD_RATE_M2_MONTH = 220.0

# S-curve shares of the construction spend, quarter by quarter of the programme.
S_CURVE = (0.10, 0.25, 0.35, 0.30)


class QuantityAgent(Agent):
    agent_id = "quantity"
    name_ar = "مساح كميات أول"
    name_en = "Senior Quantity Surveyor"
    role_ar = "حصر الكميات، خطة التكلفة العنصرية، البرنامج الزمني والتدفق النقدي"
    role_en = "Quantity take-off, elemental cost plan, programme and cashflow"
    depends_on = ("architecture", "structural", "mechanical", "electrical", "interior")

    def analyse(self, brief, ctx):
        gfa = brief["gfa"]
        footprint = brief["footprint"]
        floors = brief["floors"]
        perimeter = 2 * (brief["build_w"] + brief["build_d"])
        facade_area = perimeter * brief["floor_h"] * floors
        # Internal partitions: a planning allowance of 0.8 m of wall per m2 of floor.
        partition_area = gfa * 0.8 * brief["floor_h"] / 3.2
        wall_area = facade_area + partition_area
        open_site = max(0.0, brief["plot_area"] - footprint)

        quantities = {
            "substructure": footprint,
            "frame_slabs": gfa,
            "blockwork": wall_area,
            "external_finish": facade_area,
            "internal_finish": gfa,
            "joinery_doors": gfa,
            "mep_mech": gfa,
            "mep_elec": gfa,
            "external_works": open_site,
        }

        elements = []
        works_low = works_high = 0.0
        labels = {
            "substructure": ("أعمال الأساسات", "Substructure"),
            "frame_slabs": ("الهيكل الخرساني والبلاطات", "Frame and slabs"),
            "blockwork": ("أعمال البلوك والجدران", "Blockwork and walls"),
            "external_finish": ("تشطيبات الواجهات", "External finishes"),
            "internal_finish": ("التشطيبات الداخلية", "Internal finishes"),
            "joinery_doors": ("الأبواب والنجارة", "Doors and joinery"),
            "mep_mech": ("الأعمال الميكانيكية", "Mechanical works"),
            "mep_elec": ("الأعمال الكهربائية", "Electrical works"),
            "external_works": ("الأعمال الخارجية والتنسيق", "External works and landscaping"),
        }
        for key, rate in RATES.items():
            qty = quantities.get(key, 0.0)
            low = qty * rate["low"]
            high = qty * rate["high"]
            works_low += low
            works_high += high
            ar, en = labels[key]
            elements.append({
                "key": key,
                "ar": ar,
                "en": en,
                "quantity": round(qty, 1),
                "unit": rate["unit"],
                "rate_low": rate["low"],
                "rate_high": rate["high"],
                "cost_low": round(low),
                "cost_high": round(high),
            })

        prelims_low, prelims_high = works_low * PRELIMS_PCT, works_high * PRELIMS_PCT
        sub_low, sub_high = works_low + prelims_low, works_high + prelims_high
        cont_low, cont_high = sub_low * CONTINGENCY_PCT, sub_high * CONTINGENCY_PCT
        fees_low, fees_high = sub_low * DESIGN_FEES_PCT, sub_high * DESIGN_FEES_PCT
        net_low = sub_low + cont_low + fees_low
        net_high = sub_high + cont_high + fees_high
        vat_low, vat_high = net_low * VAT_PCT, net_high * VAT_PCT
        total_low, total_high = net_low + vat_low, net_high + vat_high

        months = max(6, int(round(gfa / BUILD_RATE_M2_MONTH)))
        # Split the programme into four periods that between them cover every
        # month. Integer division on its own leaves the tail uncovered.
        cashflow = []
        periods = len(S_CURVE)
        for i, share in enumerate(S_CURVE):
            start = months * i // periods + 1
            end = months * (i + 1) // periods
            cashflow.append({
                "period_ar": f"الربع {i + 1}",
                "period_en": f"Quarter {i + 1}",
                "months": f"{start}-{end}" if end > start else f"{start}",
                "month_from": start,
                "month_to": end,
                "share": share,
                "low": round(net_low * share),
                "high": round(net_high * share),
            })

        metrics = [
            metric("تكلفة الأعمال", "Works cost", f"{works_low:,.0f} - {works_high:,.0f}", "SAR", "elemental rates x quantities"),
            metric("المصاريف العمومية", "Preliminaries", f"{prelims_low:,.0f} - {prelims_high:,.0f}", "SAR", f"{PRELIMS_PCT:.0%} of works"),
            metric("الاحتياطي", "Contingency", f"{cont_low:,.0f} - {cont_high:,.0f}", "SAR", f"{CONTINGENCY_PCT:.0%} — concept stage"),
            metric("أتعاب التصميم والإشراف", "Design and supervision fees", f"{fees_low:,.0f} - {fees_high:,.0f}", "SAR", f"{DESIGN_FEES_PCT:.0%}"),
            metric("الإجمالي قبل الضريبة", "Total before VAT", f"{net_low:,.0f} - {net_high:,.0f}", "SAR", "works + prelims + contingency + fees"),
            metric("ضريبة القيمة المضافة", "VAT", f"{vat_low:,.0f} - {vat_high:,.0f}", "SAR", f"{VAT_PCT:.0%} — confirm the current rate"),
            metric("الإجمالي شامل الضريبة", "Total including VAT", f"{total_low:,.0f} - {total_high:,.0f}", "SAR", "indicative budget range"),
            metric("التكلفة لكل متر مربع", "Cost per m²", f"{net_low / gfa:,.0f} - {net_high / gfa:,.0f}", "SAR/m²", "before VAT, on gross floor area"),
            metric("مدة التنفيذ التقديرية", "Indicative construction period", months, "months", f"~{BUILD_RATE_M2_MONTH:g} m²/month"),
        ]

        recommendations = [
            rec(f"الميزانية الاسترشادية {rng(total_low / 1e6, total_high / 1e6, ',.2f')} مليون ريال شاملة الضريبة — استخدم الحد الأعلى للتخطيط المالي.",
                f"An indicative budget of SAR {total_low / 1e6:,.2f}-{total_high / 1e6:,.2f} million including VAT — plan against the upper bound.",
                "high"),
            rec("هذه الأسعار نطاقات تخطيطية وليست عروض أسعار — اطلب تسعيرًا من السوق قبل أي التزام تعاقدي أو وعد للعميل.",
                "These rates are planning bands, not quotations — obtain market pricing before any contractual commitment or client promise.",
                "high"),
            rec(f"احتياطي {CONTINGENCY_PCT:.0%} مناسب لمرحلة الفكرة فقط — خفّضه تدريجيًا مع نضج التصميم ولا ترفع النطاق قبل ذلك.",
                f"A {CONTINGENCY_PCT:.0%} contingency suits concept stage only — reduce it as the design matures rather than widening the scope first.",
                "medium"),
            rec("أكبر بنود عدم اليقين هي الأساسات (قبل جسّ التربة) وتشطيبات الواجهات — ثبّت مواصفاتهما مبكرًا.",
                "The biggest uncertainty sits in the substructure (before the soil investigation) and the facade finishes — fix both specifications early.",
                "medium"),
        ]

        return {
            "summary_ar": (
                f"تكلفة إنشائية استرشادية {rng(net_low / 1e6, net_high / 1e6, ',.2f')} مليون ريال قبل الضريبة "
                f"({rng(net_low / gfa, net_high / gfa)} ريال/م²) على مدى {months} شهرًا."
            ),
            "summary_en": (
                f"An indicative SAR {net_low / 1e6:,.2f}-{net_high / 1e6:,.2f} million before VAT "
                f"({net_low / gfa:,.0f}-{net_high / gfa:,.0f} SAR/m²) over {months} months."
            ),
            "metrics": metrics,
            "schedule": elements,
            "cashflow": cashflow,
            "recommendations": recommendations,
            "assumptions": [
                note("الأسعار نطاقات تخطيطية عامة غير مرتبطة بتاريخ سوق أو مورّد أو موقع محدد.",
                     "Rates are generic planning bands tied to no market date, supplier or specific location."),
                note("الكميات محصورة تقريبيًا من الهندسة العامة دون مخططات تنفيذية.",
                     "Quantities are approximate take-offs from overall geometry with no construction drawings."),
                note("لا تشمل التقديرات الأرض ولا رسوم التوصيل ولا الأثاث ولا تمويل المشروع.",
                     "The estimate excludes land, utility connection charges, furniture and project finance."),
                note("افتراض تنفيذ بمقاول رئيسي واحد بعقد تقليدي.",
                     "A single main contractor on a traditional contract is assumed."),
            ],
            "verify": [
                verify("جميع الأسعار مقابل عروض سوقية فعلية قبل أي التزام.",
                       "Every rate against actual market quotations before any commitment.", "Market pricing"),
                verify("نسبة ضريبة القيمة المضافة السارية وقت التعاقد.",
                       "The VAT rate in force at the time of contract.", "ZATCA"),
                verify("رسوم التوصيل والتصاريح لدى الجهات الخدمية والبلدية.",
                       "Connection and permit fees with the utilities and the municipality.", "SEC / NWC / Balady"),
            ],
            "outputs": {
                "works_low": round(works_low),
                "works_high": round(works_high),
                "net_low": round(net_low),
                "net_high": round(net_high),
                "total_low": round(total_low),
                "total_high": round(total_high),
                "cost_per_m2_low": round(net_low / gfa),
                "cost_per_m2_high": round(net_high / gfa),
                "months": months,
            },
        }
