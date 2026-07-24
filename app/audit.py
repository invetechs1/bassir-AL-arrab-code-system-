"""Best-effort audit logging. Failures never break the request path."""

import json
import logging

from app.db.base import SessionLocal
from app.db.models import AuditLog

logger = logging.getLogger("alarrab.audit")


def log_action(tenant_id: str, actor: str, action: str, resource: str = "", detail: dict = None) -> None:
    try:
        session = SessionLocal()
        try:
            session.add(
                AuditLog(
                    tenant_id=tenant_id or "",
                    actor=actor or "",
                    action=action,
                    resource=resource,
                    detail_json=json.dumps(detail or {}, ensure_ascii=False, default=str),
                )
            )
            session.commit()
        finally:
            session.close()
    except Exception:  # pragma: no cover - audit must never break requests
        logger.exception("audit log write failed")
