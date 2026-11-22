"""Phase 1 orchestrator boundary for goal planning.

The orchestrator creates a declarative plan only. Tool registration and tool
execution are intentionally deferred to Phases 2 and 3.
"""

from dataclasses import dataclass

from app.agents.planner import create_plan
from app.agents.schemas import AgentPlanProposal
from app.core.config import Settings


@dataclass(frozen=True)
class AgentPlanningResult:
    """Validated planner output and the effective provider/model metadata."""

    proposal: AgentPlanProposal
    provider: str
    model: str


class AgentOrchestrator:
    """Coordinate goal planning while keeping execution out of Phase 1."""

    async def plan_goal(self, goal: str, *, max_steps: int) -> AgentPlanningResult:
        proposal, settings = await create_plan(goal, max_steps=max_steps)
        return AgentPlanningResult(
            proposal=proposal,
            provider=settings.llm_provider.strip().lower(),
            model=settings.llm_model.strip(),
        )
