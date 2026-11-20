"""Narrow, read-only integration façade for the JARVIS application."""

from pathlib import Path

from .runtime import TestarossaRuntime


class JarvisTestarossaAdapter:
    """Expose approved intelligence operations without bypassing JARVIS controls."""

    def __init__(self, observer, memory_directory):
        if not callable(observer):
            raise ValueError("observer_must_be_callable")

        memory_root = Path(memory_directory)
        memory_root.mkdir(parents=True, exist_ok=True)

        self._runtime = TestarossaRuntime(
            observer=observer,
            memory_directory=memory_root,
        )

    def discover_tools(self, capability=None, include_mutations=False):
        return self._runtime.discover_tools(
            capability=capability,
            include_mutations=include_mutations,
        )

    def validate_plan(self, proposal):
        plan = self._runtime.validate_plan(proposal)
        return plan.as_dict() if hasattr(plan, "as_dict") else plan

    def inspect_scene(self, goal="Testarossa scene inspection"):
        return self._runtime.execute_read_tool(
            "inspect_scene",
            {},
            goal=goal,
            stage="jarvis_scene_inspection",
        )

    def inspect_project(self, goal="Testarossa project inspection"):
        return self._runtime.execute_read_tool(
            "inspect_project",
            {},
            goal=goal,
            stage="jarvis_project_inspection",
        )

    def analyze_scene(self, goal="Testarossa scene analysis"):
        return self._runtime.execute_read_tool(
            "analyze_blender_scene",
            {},
            goal=goal,
            stage="jarvis_scene_analysis",
        )

    def analyze_project(self, goal="Testarossa project analysis"):
        return self._runtime.execute_read_tool(
            "analyze_blender_project",
            {},
            goal=goal,
            stage="jarvis_project_analysis",
        )

    def record_outcome(
        self, goal, stage, outcome, summary, error_code=None
    ):
        return self._runtime.record_outcome(
            goal=goal,
            stage=stage,
            outcome=outcome,
            summary=summary,
            error_code=error_code,
        )

    def recent_experiences(self, limit=20):
        return self._runtime.recent_experiences(limit=limit)

    def learning_summary(self, limit=100):
        return self._runtime.learning_summary(limit=limit)

    def recovery_advice(
        self, outcome, error="", retry_count=0, approval_required=False
    ):
        return self._runtime.recovery_advice(
            outcome=outcome,
            error=error,
            retry_count=retry_count,
            approval_required=approval_required,
        )

    def search_skills(self, query, limit=10):
        return self._runtime.search_skills(query=query, limit=limit)

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
        return self._runtime.save_reviewed_skill(
            name=name,
            title=title,
            purpose=purpose,
            prerequisites=prerequisites,
            steps=steps,
            verification=verification,
            user_approved=user_approved,
            tags=tags,
        )


def create_adapter(observer, memory_directory):
    """Factory used by the host application to inject its authenticated observer."""
    return JarvisTestarossaAdapter(observer, memory_directory)
