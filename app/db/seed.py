"""Seed the database with a demo tenant, admin user, and draft rules.

Never seeds in production unless SEED_DEMO_DATA=true is set explicitly.
The admin password comes from SEED_ADMIN_PASSWORD (a random one is
generated and printed once if unset — never hardcoded).
"""

import json
import os
import secrets

from app.config import settings
from app.db.base import SessionLocal, init_db
from app.db.models import PolicyProfile, Rule, Tenant, User
from app.engine.rules_store import load_seed_rules
from app.security.auth import hash_password


def seed() -> dict:
    init_db()
    session = SessionLocal()
    summary = {"tenant": None, "admin": None, "rules": 0, "note": ""}
    try:
        tenant = session.query(Tenant).filter_by(name="Demo Engineering Office").first()
        if tenant is None:
            tenant = Tenant(id="demo", name="Demo Engineering Office", plan="pilot")
            session.add(tenant)
        summary["tenant"] = tenant.id

        admin = session.query(User).filter_by(email="admin@demo.local").first()
        if admin is None:
            password = os.environ.get("SEED_ADMIN_PASSWORD") or secrets.token_urlsafe(12)
            admin = User(
                tenant_id=tenant.id,
                email="admin@demo.local",
                full_name="Demo Admin",
                password_hash=hash_password(password),
                role="admin",
            )
            session.add(admin)
            if not os.environ.get("SEED_ADMIN_PASSWORD"):
                summary["note"] = f"generated admin password (store it now): {password}"
        summary["admin"] = admin.email

        for rule_dict in load_seed_rules():
            existing = session.query(Rule).filter_by(code=rule_dict["code"]).first()
            if existing:
                continue
            gov = rule_dict.get("governance", {})
            session.add(
                Rule(
                    code=rule_dict["code"],
                    title_ar=rule_dict["title_ar"],
                    title_en=rule_dict["title_en"],
                    category=rule_dict["category"],
                    severity=rule_dict.get("severity", "medium"),
                    check_json=json.dumps(rule_dict.get("check", {})),
                    source_reference=gov.get("source_reference", ""),
                    clause=gov.get("clause", ""),
                    last_reviewed_date=gov.get("last_reviewed_date", ""),
                    confidence_level=gov.get("confidence_level", "draft"),
                    validated_by=gov.get("validated_by", "") or "",
                    status=rule_dict.get("status", "draft"),
                    is_active=False,  # draft rules are NEVER auto-activated
                )
            )
            summary["rules"] += 1

        profile = session.query(PolicyProfile).filter_by(tenant_id=tenant.id).first()
        if profile is None:
            session.add(
                PolicyProfile(
                    tenant_id=tenant.id,
                    name="Default preliminary review",
                    description="All draft preliminary checks (non-official).",
                    rule_codes_json=json.dumps(
                        [r["code"] for r in load_seed_rules()]
                    ),
                    is_default=True,
                )
            )
        session.commit()
    finally:
        session.close()
    return summary


if __name__ == "__main__":
    if settings.is_production and os.environ.get("SEED_DEMO_DATA", "").lower() != "true":
        raise SystemExit("Refusing to seed demo data in production without SEED_DEMO_DATA=true")
    print(json.dumps(seed(), ensure_ascii=False, indent=2))
