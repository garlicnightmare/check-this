"""Tool discovery and relevance ranking. Discovery never executes tools."""
from dataclasses import dataclass
from .registry import TOOLS, Tool


@dataclass(frozen=True)
class DiscoveryResult:
    tool: Tool
    score: int
    matched_terms: tuple[str, ...]


def _terms(value: str) -> set[str]:
    return {
        part.strip(".,!?():;[]{}\"'").lower()
        for part in value.split()
        if len(part.strip(".,!?():;[]{}\"'")) > 1
    }


class ToolDiscovery:
    def __init__(self, tools=TOOLS):
        self._tools = tuple(tools)

    def discover(
        self,
        query: str,
        capability: str | None = None,
        include_mutations: bool = False,
        limit: int = 8,
    ) -> list[DiscoveryResult]:
        if type(query) is not str or len(query) > 500:
            raise ValueError("invalid_query")
        if capability is not None and (
            type(capability) is not str or len(capability) > 100
        ):
            raise ValueError("invalid_capability")
        if type(include_mutations) is not bool:
            raise ValueError("invalid_mutation_filter")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("invalid_limit")

        wanted = _terms(query)
        results = []

        for tool in self._tools:
            if not tool.enabled:
                continue
            if capability and tool.capability != capability:
                continue
            if not include_mutations and (
                tool.approval_required or tool.risk != "read"
            ):
                continue

            searchable = (
                f"{tool.name} {tool.description} "
                f"{tool.capability} {' '.join(tool.arguments)}"
            )
            available = _terms(searchable)
            matched = wanted & available
            score = len(matched)

            if capability:
                score += 5
            if tool.name.lower().replace("_", " ") in query.lower():
                score += 4

            if score:
                results.append(
                    DiscoveryResult(
                        tool=tool,
                        score=score,
                        matched_terms=tuple(sorted(matched)),
                    )
                )

        results.sort(key=lambda item: (-item.score, item.tool.name))
        return results[:limit]
