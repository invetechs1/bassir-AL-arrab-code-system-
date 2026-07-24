"""Regulatory resource catalog loader and summary."""

import json
from functools import lru_cache

from app.config import settings

REQUIRED_RESOURCE_FIELDS = (
    "id", "title_ar", "title_en", "issuer", "type", "priority",
    "status", "binding", "source_reference", "last_reviewed_date",
    "confidence_level",
)

NON_BINDING_STATUSES = ("draft", "consultation")


@lru_cache(maxsize=1)
def _load() -> dict:
    path = settings.data_dir / "regulatory_resource_catalog.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def list_resources() -> list:
    resources = []
    for res in _load()["resources"]:
        entry = dict(res)
        # Defense in depth: a draft/consultation source can never be binding,
        # regardless of what the JSON claims.
        if entry.get("status") in NON_BINDING_STATUSES:
            entry["binding"] = False
        resources.append(entry)
    return resources


def validate_catalog() -> list:
    """Return a list of problems (empty = catalog is well-formed)."""
    problems = []
    seen = set()
    for res in _load()["resources"]:
        rid = res.get("id", "<missing-id>")
        if rid in seen:
            problems.append(f"duplicate resource id: {rid}")
        seen.add(rid)
        for field in REQUIRED_RESOURCE_FIELDS:
            if field not in res or res[field] in (None, ""):
                problems.append(f"{rid}: missing field '{field}'")
        if res.get("status") in NON_BINDING_STATUSES and res.get("binding"):
            problems.append(f"{rid}: {res.get('status')} source must not be binding")
        if res.get("priority") not in ("P0", "P1", "P2"):
            problems.append(f"{rid}: invalid priority '{res.get('priority')}'")
    return problems


def summary() -> dict:
    resources = list_resources()
    by_priority, by_status, by_issuer = {}, {}, {}
    for res in resources:
        by_priority[res["priority"]] = by_priority.get(res["priority"], 0) + 1
        by_status[res["status"]] = by_status.get(res["status"], 0) + 1
        by_issuer[res["issuer"]] = by_issuer.get(res["issuer"], 0) + 1
    return {
        "total": len(resources),
        "binding": sum(1 for r in resources if r["binding"]),
        "non_binding": sum(1 for r in resources if not r["binding"]),
        "by_priority": by_priority,
        "by_status": by_status,
        "by_issuer": by_issuer,
        "priorities_legend": _load().get("priorities", {}),
        "catalog_problems": validate_catalog(),
    }
