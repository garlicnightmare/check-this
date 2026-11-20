"""Narrow read-only executor for explicitly prepared Blender intelligence calls.

The ToolGateway remains a validator/preparer and has no execution facility.
This executor accepts only its prepared read-only calls and invokes only
four fixed Blender inspection/analysis operations through an injected
observer function.
"""

from .gateway import PreparedCall, ToolGateway
from .blender_intelligence import BlenderSceneAnalyzer


class ReadOnlyToolExecutor:
    ALLOWED = {
        "inspect_scene": "scene",
        "inspect_project": "project",
        "analyze_blender_scene": "analyze_scene",
        "analyze_blender_project": "analyze_project",
    }

    def __init__(self, observer, analyzer=None):
        if not callable(observer):
            raise ValueError("observer_must_be_callable")
        self._observer = observer
        self._analyzer = analyzer or BlenderSceneAnalyzer()
        self._gateway = ToolGateway()

    def execute(self, prepared):
        if not isinstance(prepared, PreparedCall):
            raise ValueError("prepared_call_required")

        if prepared.tool_name not in self.ALLOWED:
            raise PermissionError("operation_not_allowlisted")

        # Revalidate the exact arguments and risk metadata. This executor
        # does not accept a caller-supplied approval override.
        validated = self._gateway.prepare(
            prepared.tool_name,
            prepared.arguments,
            user_approved=False,
        )

        if (
            validated.capability != prepared.capability
            or validated.risk != "read"
            or prepared.risk != "read"
            or validated.approval_required
            or prepared.approval_required
            or prepared.approved
        ):
            raise PermissionError("read_only_boundary_violation")

        operation = self.ALLOWED[prepared.tool_name]

        if operation in ("scene", "analyze_scene"):
            snapshot = self._observer("blender_scene_snapshot")
            if operation == "scene":
                return snapshot
            return self._analyzer.analyze_scene(snapshot)

        snapshot = self._observer("blender_project_snapshot")
        if operation == "project":
            return snapshot
        return self._analyzer.analyze_project(snapshot)
