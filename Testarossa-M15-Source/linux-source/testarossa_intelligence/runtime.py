"""Coordinating runtime for Testarossa's isolated intelligence foundation.

The runtime validates plans, discovers registered capabilities, and routes
only explicitly allowlisted Blender read operations to ReadOnlyToolExecutor.

It does not execute arbitrary tools, run generated code, or perform mutations.
"""
from pathlib import Path
from typing import Any

from .gateway import ToolGateway
from .learning import LearningEngine
from .memory import ExperienceLog, SkillLibrary
from .planner import Plan, validate_plan
from .read_executor import ReadOnlyToolExecutor
from .registry import Registry


class TestarossaRuntime:
    """Safe coordinator around planning, memory, and read-only execution."""

    READ_EXECUTABLE_TOOLS = frozenset(ReadOnlyToolExecutor.ALLOWED)

    def __init__(
        self,
        observer,
        memory_directory,
        registry=None,
        executor=None,
    ):
        if not callable(observer) and executor is None:
            raise ValueError("observer_must_be_callable")

        self.registry = registry or Registry()
        self.gateway = ToolGateway()
        self.executor = executor or ReadOnlyToolExecutor(observer)

        root = Path(memory_directory)
        self.skills = SkillLibrary(root / "skills")
        self.experiences = ExperienceLog(root / "experiences")
        self.learning = LearningEngine()

    def discover_tools(self, capability=None, include_mutations=False):
        """Return registered tools without granting execution permission."""
        if capability is not None and (
            type(capability) is not str or not capability.strip()
        ):
            raise ValueError("invalid_capability")

        tools = self.registry.describe(capability=capability)
        if not include_mutations:
            tools = [tool for tool in tools if tool["risk"] == "read"]
        return tools

    def validate_plan(self, proposal):
        """Validate a model-proposed plan against registered capabilities."""
        capabilities = {
            item["capability"]
            for item in self.registry.describe()
        }
        return validate_plan(proposal, capabilities)

    def execute_read_tool(
        self,
        tool_name,
        arguments,
        goal="Blender inspection",
        stage="read_execution",
    ):
        """Execute one explicitly allowlisted read-only Blender operation."""
        if type(tool_name) is not str:
            raise ValueError("invalid_tool_name")
        if tool_name not in self.READ_EXECUTABLE_TOOLS:
            raise PermissionError("runtime_tool_not_executable")

        tool = self.registry.get(tool_name)
        if tool.risk != "read" or tool.approval_required:
            raise PermissionError("runtime_read_only_boundary")

        prepared = self.gateway.prepare(tool_name, arguments)

        try:
            result = self.executor.execute(prepared)
        except Exception as exc:
            self.experiences.record(
                goal=goal,
                stage=stage,
                outcome="failure",
                summary="Read-only operation failed; no automatic retry was attempted.",
                error_code=type(exc).__name__[:80],
            )
            raise

        self.experiences.record(
            goal=goal,
            stage=stage,
            outcome="success",
            summary="Read-only operation completed; result returned for inspection.",
        )
        return result

    def execute_plan_step(
        self,
        plan,
        step_id,
        tool_name,
        arguments,
    ):
        """Execute a plan step only when its declared capability matches.

        Approval-required steps are deliberately not executed by this runtime.
        A future mutation executor must be separately integrated with the
        existing user approval and broker workflow.
        """
        if not isinstance(plan, Plan):
            raise ValueError("validated_plan_required")
        if type(step_id) is not str or type(tool_name) is not str:
            raise ValueError("invalid_step_selection")

        step = next((item for item in plan.steps if item.id == step_id), None)
        if step is None:
            raise ValueError("plan_step_not_found")

        tool = self.registry.get(tool_name)
        if tool.capability != step.capability:
            raise PermissionError("plan_tool_capability_mismatch")

        if step.requires_user_approval:
            raise PermissionError("plan_step_requires_approval")

        if tool_name not in self.READ_EXECUTABLE_TOOLS:
            raise PermissionError("plan_step_not_read_executable")

        return self.execute_read_tool(
            tool_name,
            arguments,
            goal=plan.goal,
            stage=step.id,
        )

    def record_outcome(
        self,
        goal,
        stage,
        outcome,
        summary,
        error_code=None,
    ):
        """Record a bounded experience; this never triggers an action."""
        return self.experiences.record(
            goal, stage, outcome, summary, error_code
        )

    def recent_experiences(self, limit=20):
        return self.experiences.recent(limit)

    def learning_summary(self, limit=100):
        """Summarize recorded outcomes for controlled learning."""
        records = self.experiences.recent(limit)
        normalized = [
            {
                "outcome": item["outcome"],
                "error": item.get("error_code") or "",
                "operation": item["stage"],
            }
            for item in records
        ]
        return self.learning.analyze_history(normalized)

    def recovery_advice(
        self,
        outcome,
        error="",
        retry_count=0,
        approval_required=False,
    ):
        """Return advice only; never retry or repair automatically."""
        return self.learning.recommend_recovery(
            outcome,
            error=error,
            retry_count=retry_count,
            approval_required=approval_required,
        )

    def search_skills(self, query, limit=10):
        return self.skills.search(query, limit)

    def save_reviewed_skill(
        self,
        name,
        title,
        purpose,
        prerequisites,
        steps,
        verification,
        user_approved,
        tags=(),
    ):
        """Save a skill only after an explicit approval boolean is supplied."""
        if type(user_approved) is not bool:
            raise ValueError("approval_must_be_boolean")
        if not user_approved:
            raise PermissionError("explicit_user_approval_required")
        return self.skills.add(
            name=name,
            title=title,
            purpose=purpose,
            prerequisites=prerequisites,
            steps=steps,
            verification=verification,
            tags=tags,
        )
