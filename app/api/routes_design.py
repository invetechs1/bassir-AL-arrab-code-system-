"""Design by Alarrab: the seven senior discipline agents.

Runs architecture, structural, mechanical, electrical, interior, quantity
surveying and regulation review over one project record, then reports the
cross-discipline coordination clashes between their outputs.

Output is advisory concept-stage analysis. It is not an approved design
and it is not an official regulatory review.
"""

from fastapi import APIRouter, Depends

from app.agents import list_agents, run_design
from app.api.deps import require
from app.api.schemas import DesignByAlarrabRequest
from app.audit import log_action

router = APIRouter(prefix="/v1/design", tags=["design-by-alarrab"])


@router.get("/alarrab/agents")
def alarrab_agents(principal=Depends(require("design:use"))):
    """Roster of the seven agents and their dependency order."""
    log_action(principal.tenant_id, principal.subject, "design.alarrab.agents")
    return list_agents()


@router.post("/alarrab")
def alarrab_design(
    body: DesignByAlarrabRequest,
    principal=Depends(require("design:use")),
):
    """Run the full seven-agent design package over a project record."""
    package = run_design(body.model_dump(exclude_none=True))
    log_action(principal.tenant_id, principal.subject, "design.alarrab.run")
    return package
