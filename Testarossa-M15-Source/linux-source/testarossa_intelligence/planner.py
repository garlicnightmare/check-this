"""Strict, deterministic validation for model-proposed task plans."""
from dataclasses import dataclass
from typing import Any
import re

_ID = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_MAX_STEPS = 32


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    description: str
    capability: str
    depends_on: tuple[str, ...]
    verification: str
    requires_user_approval: bool


@dataclass(frozen=True)
class Plan:
    goal: str
    steps: tuple[Step, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [
                {
                    "id": s.id,
                    "title": s.title,
                    "description": s.description,
                    "capability": s.capability,
                    "depends_on": list(s.depends_on),
                    "verification": s.verification,
                    "requires_user_approval": s.requires_user_approval,
                } for s in self.steps
            ],
        }


def validate_plan(value: dict, allowed_capabilities: set[str]) -> Plan:
    if type(value) is not dict or set(value) != {"goal", "steps"}:
        raise ValueError("invalid_plan_fields")
    goal = value["goal"]
    raw_steps = value["steps"]
    if type(goal) is not str or not 1 <= len(goal.strip()) <= 1000:
        raise ValueError("invalid_goal")
    if type(raw_steps) is not list or not 1 <= len(raw_steps) <= _MAX_STEPS:
        raise ValueError("invalid_step_count")

    steps = []
    seen = set()
    for raw in raw_steps:
        fields = {
            "id", "title", "description", "capability",
            "depends_on", "verification", "requires_user_approval"
        }
        if type(raw) is not dict or set(raw) != fields:
            raise ValueError("invalid_step_fields")
        sid = raw["id"]
        if type(sid) is not str or not _ID.fullmatch(sid) or sid in seen:
            raise ValueError("invalid_step_id")
        seen.add(sid)
        for key, limit in (("title", 120), ("description", 1000),
                           ("verification", 500), ("capability", 80)):
            item = raw[key]
            if type(item) is not str or not item.strip() or len(item) > limit:
                raise ValueError("invalid_" + key)
        if raw["capability"] not in allowed_capabilities:
            raise ValueError("capability_not_available")
        deps = raw["depends_on"]
        if type(deps) is not list or len(deps) > _MAX_STEPS:
            raise ValueError("invalid_dependencies")
        if any(type(dep) is not str for dep in deps) or len(set(deps)) != len(deps):
            raise ValueError("invalid_dependencies")
        if type(raw["requires_user_approval"]) is not bool:
            raise ValueError("invalid_approval_flag")
        steps.append(Step(
            sid, raw["title"], raw["description"], raw["capability"],
            tuple(deps), raw["verification"], raw["requires_user_approval"]
        ))

    ids = {step.id for step in steps}
    for step in steps:
        if step.id in step.depends_on or any(dep not in ids for dep in step.depends_on):
            raise ValueError("unknown_or_self_dependency")

    # Topological validation: cycles are rejected; original order is retained.
    completed = set()
    pending = list(steps)
    while pending:
        ready = [s for s in pending if set(s.depends_on) <= completed]
        if not ready:
            raise ValueError("dependency_cycle")
        for step in ready:
            completed.add(step.id)
            pending.remove(step)

    return Plan(goal.strip(), tuple(steps))
