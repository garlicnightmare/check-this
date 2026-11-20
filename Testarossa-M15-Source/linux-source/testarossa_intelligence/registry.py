"""Declarative tool catalogue. Descriptions never grant execution permission."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments: tuple[str, ...]
    capability: str
    risk: str
    approval_required: bool
    enabled: bool = True


TOOLS = (
    Tool("inspect_workstation", "Inspect approved workstation status", (),
         "computer.read", "read", False),
    Tool("inspect_blender", "Inspect Blender installation and process", (),
         "blender.read", "read", False),
    Tool("inspect_scene", "Inspect the active Blender scene", (),
         "blender.read", "read", False),
    Tool("inspect_project", "Inspect the open Blender project", (),
         "blender.read", "read", False),
    Tool("analyze_blender_scene",
         "Analyze Blender scene structure, character components, and production pipeline",
         (), "blender.analyze", "read", False),
    Tool("analyze_blender_project",
         "Analyze Blender project inventory, scenes, materials, and animation actions",
         (), "blender.analyze", "read", False),
    Tool("list_workspace_files", "List files in the approved workspace", ("path",),
         "workspace.read", "read", False),
    Tool("read_workspace_file", "Read a file in the approved workspace", ("path",),
         "workspace.read", "read", False),
    Tool("validate_python", "Validate Python syntax without executing it", ("path",),
         "code.validate", "read", False),
    Tool("propose_file_change", "Prepare a file change for user review", 
         ("path", "content", "expected_sha256"),
         "workspace.write", "mutation", True),
    Tool("propose_directory", "Prepare directory creation for user review", ("path",),
         "workspace.write", "mutation", True),
    Tool("testarossa_propose_blender_plan",
         "Prepare a typed Blender project plan for explicit user approval; never executes directly.",
         ("plan",), "blender.write", "mutation", True),
)


class Registry:
    def __init__(self, tools=TOOLS):
        self._tools = {tool.name: tool for tool in tools}
        if len(self._tools) != len(tools):
            raise ValueError("duplicate_tool")

    def get(self, name: str) -> Tool:
        try:
            tool = self._tools[name]
        except (KeyError, TypeError):
            raise ValueError("tool_not_registered") from None
        if not tool.enabled:
            raise ValueError("tool_disabled")
        return tool

    def describe(self, capability: str | None = None) -> list[dict[str, Any]]:
        result = []
        for tool in self._tools.values():
            if not tool.enabled:
                continue
            if capability and tool.capability != capability:
                continue
            result.append({
                "name": tool.name,
                "description": tool.description,
                "arguments": list(tool.arguments),
                "capability": tool.capability,
                "risk": tool.risk,
                "approval_required": tool.approval_required,
            })
        return result

    def validate_invocation(self, name: str, arguments: dict) -> Tool:
        tool = self.get(name)
        if type(arguments) is not dict or set(arguments) != set(tool.arguments):
            raise ValueError("invalid_tool_arguments")
        return tool
