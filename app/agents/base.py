"""Shared foundation for the seven senior discipline agents.

Every agent is deterministic: the same brief always produces the same
package. No value produced here is an official Saudi Building Code
requirement. Agents encode ordinary professional planning heuristics
(span/depth ratios, VA/m2 allowances, m2/TR rules of thumb, elemental
cost ranges) that a senior engineer would use for a concept-stage sanity
check, and every one of them is reported with the basis it came from and
a matching entry in the agent's `verify` register.

The governance invariants in the README apply unchanged: nothing an agent
emits is binding, and nothing here may be presented as a code clause.
"""

from app.legal import disclaimer

SENIORITY = "senior"

# Unicode directional isolates. A tight numeric range such as "12.65-23.29"
# embedded in Arabic prose renders with its ends swapped under an RTL base
# direction (verified in Chromium), which silently turns a cost range of
# 12.65-23.29 million into 23.29-12.65. Wrapping the run in LRI...PDI pins it
# to LTR order. The two characters are invisible and change no glyph, so the
# same string is safe in HTML, a terminal, or a generated document.
LRI = "\u2066"
PDI = "\u2069"


def ltr(text) -> str:
    """Pin a Latin/numeric run to LTR order inside bidirectional prose."""
    return f"{LRI}{text}{PDI}"


def rng(low, high, spec=",.0f") -> str:
    """Format a low-high range as one isolated LTR run."""
    return ltr(f"{low:{spec}}-{high:{spec}}")

# Priority bands for recommendations, mirroring the assessment engine's
# severity vocabulary so the UI can reuse the same styling.
PRIORITIES = ("high", "medium", "low")


def _num(value, default=0.0):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result != result or result in (float("inf"), float("-inf")):
        return default
    return result


def metric(key_ar, key_en, value, unit="", basis=""):
    """One calculated figure with the heuristic it came from."""
    return {
        "key_ar": key_ar,
        "key_en": key_en,
        "value": value,
        "unit": unit,
        "basis": basis,
    }


def rec(ar, en, priority="medium"):
    if priority not in PRIORITIES:
        priority = "medium"
    return {"ar": ar, "en": en, "priority": priority}


def note(ar, en):
    return {"ar": ar, "en": en}


def verify(ar, en, source=""):
    """An item the agent explicitly refuses to treat as settled."""
    return {"ar": ar, "en": en, "source": source}


def build_brief(params: dict) -> dict:
    """Normalise the project record into the brief every agent reads.

    Geometry mirrors geom() in web/app.js so the server and the browser
    describe the same building.
    """
    params = params or {}
    plot_w = max(6.0, _num(params.get("plot_w"), 20.0))
    plot_d = max(6.0, _num(params.get("plot_d"), 25.0))
    sb_f = max(0.0, _num(params.get("sb_f"), 3.0))
    sb_s = max(0.0, _num(params.get("sb_s"), 2.0))
    sb_r = max(0.0, _num(params.get("sb_r"), 2.0))

    floors = max(1, int(round(_num(params.get("floors"), 2.0))) or 1)
    floor_h = max(2.4, _num(params.get("floor_h"), 3.2))
    units = max(1, int(round(_num(params.get("units"), 1.0))) or 1)
    parking = max(0, int(round(_num(params.get("parking"), 2.0))))

    plot_area = plot_w * plot_d
    build_w = max(2.0, plot_w - 2 * sb_s)
    build_d = max(2.0, plot_d - sb_f - sb_r)
    footprint = build_w * build_d
    gfa = footprint * floors

    land_use = str(params.get("land_use") or "residential").strip().lower()
    building_type = str(params.get("building_type") or "villa").strip().lower()
    city = str(params.get("city") or "").strip()

    return {
        "project_name": str(params.get("project_name") or "").strip(),
        "city": city,
        "office": str(params.get("office") or "").strip(),
        "land_use": land_use,
        "building_type": building_type,
        "plot_w": plot_w,
        "plot_d": plot_d,
        "sb_f": sb_f,
        "sb_s": sb_s,
        "sb_r": sb_r,
        "plot_area": plot_area,
        "build_w": build_w,
        "build_d": build_d,
        "footprint": footprint,
        "floors": floors,
        "floor_h": floor_h,
        "units": units,
        "parking": parking,
        "gfa": gfa,
        "coverage": footprint / plot_area if plot_area else 0.0,
        "far": gfa / plot_area if plot_area else 0.0,
        "height": floors * floor_h + 1.0,
    }


class Agent:
    """Base class for a senior discipline agent.

    Subclasses set the identity fields and implement `analyse(brief, ctx)`,
    returning the discipline-specific body. `run` wraps that body in the
    envelope every agent shares.
    """

    agent_id = "agent"
    name_ar = ""
    name_en = ""
    role_ar = ""
    role_en = ""
    depends_on = ()

    def analyse(self, brief: dict, ctx: dict) -> dict:
        raise NotImplementedError

    def run(self, brief: dict, ctx: dict = None) -> dict:
        ctx = ctx if ctx is not None else {}
        body = self.analyse(brief, ctx) or {}
        package = {
            "agent_id": self.agent_id,
            "seniority": SENIORITY,
            "name_ar": self.name_ar,
            "name_en": self.name_en,
            "role_ar": self.role_ar,
            "role_en": self.role_en,
            "depends_on": list(self.depends_on),
            "advisory_only": True,
            "official_basis": False,
            "metrics": [],
            "schedule": [],
            "recommendations": [],
            "assumptions": [],
            "verify": [],
        }
        package.update(body)
        return package


def package_envelope(kind: str, extra: dict = None) -> dict:
    """Standard non-official wrapper shared by the agent endpoints."""
    envelope = {
        "kind": kind,
        "advisory_only": True,
        "official_basis": False,
        "note_ar": (
            "مخرجات استرشادية لمرحلة الفكرة التصميمية أنتجتها وكلاء تحليل آلية. "
            "ليست تصميمًا هندسيًا معتمدًا ولا فحصًا نظاميًا رسميًا، ويجب مراجعتها "
            "واعتمادها من مهندسين مرخصين قبل أي استخدام."
        ),
        "note_en": (
            "Indicative concept-stage output produced by automated analysis agents. "
            "It is not an approved engineering design or an official regulatory "
            "review, and must be checked and signed off by licensed engineers "
            "before any use."
        ),
        "disclaimer": disclaimer(),
    }
    envelope.update(extra or {})
    return envelope
