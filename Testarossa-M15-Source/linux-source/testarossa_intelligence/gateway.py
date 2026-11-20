"""Strict call preparation. This module deliberately has no execution facility."""
from dataclasses import dataclass
import math
from .registry import TOOLS


@dataclass(frozen=True)
class PreparedCall:
    tool_name: str
    arguments: dict
    capability: str
    risk: str
    approval_required: bool
    approved: bool


def _validate_value(value, depth=0):
    if depth > 6:
        raise ValueError("argument_too_deep")

    if value is None or type(value) in (bool, int, str):
        if type(value) is str and len(value) > 4000:
            raise ValueError("argument_string_too_long")
        return

    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non_finite_number")
        return

    if type(value) is list:
        if len(value) > 100:
            raise ValueError("argument_list_too_large")
        for item in value:
            _validate_value(item, depth + 1)
        return

    if type(value) is dict:
        if len(value) > 100:
            raise ValueError("argument_object_too_large")
        for key, item in value.items():
            if type(key) is not str or len(key) > 100:
                raise ValueError("invalid_argument_key")
            _validate_value(item, depth + 1)
        return

    raise ValueError("unsupported_argument_type")


class ToolGateway:
    """Validates and prepares tool calls; it never invokes an executor."""

    def __init__(self, tools=TOOLS):
        self._tools = {tool.name: tool for tool in tools}

    def prepare(
        self,
        tool_name: str,
        arguments: dict,
        user_approved: bool = False,
    ) -> PreparedCall:
        if type(tool_name) is not str or len(tool_name) > 100:
            raise ValueError("invalid_tool_name")
        tool = self._tools.get(tool_name)
        if tool is None or not tool.enabled:
            raise ValueError("tool_unavailable")

        if type(arguments) is not dict:
            raise ValueError("arguments_must_be_object")

        expected = set(tool.arguments)
        supplied = set(arguments)
        if supplied != expected:
            raise ValueError("argument_schema_mismatch")

        for value in arguments.values():
            _validate_value(value)

        needs_approval = (
            tool.approval_required or tool.risk != "read"
        )
        if type(user_approved) is not bool:
            raise ValueError("approval_must_be_boolean")
        if needs_approval and not user_approved:
            raise PermissionError("explicit_user_approval_required")

        return PreparedCall(
            tool_name=tool.name,
            arguments=dict(arguments),
            capability=tool.capability,
            risk=tool.risk,
            approval_required=needs_approval,
            approved=user_approved if needs_approval else False,
        )
