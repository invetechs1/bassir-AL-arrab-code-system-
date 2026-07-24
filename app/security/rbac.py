"""Role definitions and permission mapping."""

ROLES = ("admin", "engineer", "reviewer", "viewer")

ROLE_PERMISSIONS = {
    "admin": {
        "assess:run", "assess:file", "assistant:use", "design:use",
        "permit:use", "bim:use", "report:generate", "rules:read",
        "governance:read", "governance:review", "governance:export",
        "system:read", "users:manage",
    },
    "engineer": {
        "assess:run", "assess:file", "assistant:use", "design:use",
        "permit:use", "bim:use", "report:generate", "rules:read",
        "governance:read", "system:read",
    },
    "reviewer": {
        "rules:read", "governance:read", "governance:review",
        "governance:export", "system:read",
    },
    "viewer": {"rules:read", "governance:read", "system:read"},
}


def permissions_for(roles) -> set:
    granted = set()
    for role in roles:
        granted |= ROLE_PERMISSIONS.get(role, set())
    return granted


def has_permission(roles, permission: str) -> bool:
    return permission in permissions_for(roles)
