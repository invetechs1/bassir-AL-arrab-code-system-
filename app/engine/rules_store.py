"""Load and expose the draft rule set.

The JSON seed file is the canonical rule source for the MVP; the Rule
DB table mirrors it for the SaaS growth path. A rule is `official` only
when ALL governance fields are present AND a professional has validated
it — which is never true for the shipped seed set.
"""

import json
from functools import lru_cache

from app.config import settings

REQUIRED_GOVERNANCE_FIELDS = (
    "source_reference",
    "clause",
    "last_reviewed_date",
    "confidence_level",
    "validated_by",
)


def is_official(rule: dict) -> bool:
    gov = rule.get("governance", {})
    if rule.get("status") != "validated":
        return False
    return all(gov.get(field) for field in REQUIRED_GOVERNANCE_FIELDS)


@lru_cache(maxsize=1)
def _load_raw() -> dict:
    path = settings.data_dir / "rules_seed.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_seed_rules() -> list:
    return _load_raw()["rules"]


def list_rules() -> list:
    rules = []
    for rule in load_seed_rules():
        entry = dict(rule)
        entry["is_official"] = is_official(rule)
        entry["is_active"] = False if not entry["is_official"] else entry.get("is_active", False)
        rules.append(entry)
    return rules


def get_rule(code: str):
    for rule in list_rules():
        if rule["code"] == code:
            return rule
    return None
