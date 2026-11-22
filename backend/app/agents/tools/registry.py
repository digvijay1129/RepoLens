"""Schema-validated registry for safe agent tool execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.models.repository import Repository


class AgentToolError(RuntimeError):
    """Safe error raised when an agent tool cannot be validated or executed."""


@dataclass(frozen=True)
class AgentToolContext:
    """Authenticated execution context supplied by the API, never the LLM."""

    db: Session
    repository: Repository
    user_id: UUID


ToolHandler = Callable[[AgentToolContext, BaseModel], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class AgentToolDefinition:
    """One read-only tool with a strict Pydantic argument contract."""

    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: ToolHandler
    read_only: bool = True


class AgentToolRegistry:
    """Allowlisted registry that validates every argument before handler dispatch."""

    def __init__(self) -> None:
        self._tools: dict[str, AgentToolDefinition] = {}

    def register(self, definition: AgentToolDefinition) -> None:
        if not definition.name or not definition.name.replace("_", "").isalnum():
            raise ValueError("Tool names must use letters, digits and underscores.")
        if definition.name in self._tools:
            raise ValueError(f"Tool '{definition.name}' is already registered.")
        if not definition.read_only:
            raise ValueError("Only read-only tools may be registered in Phase 2.")
        self._tools[definition.name] = definition

    def get(self, name: str) -> AgentToolDefinition:
        definition = self._tools.get(name)
        if definition is None:
            raise AgentToolError("The agent requested a tool that is not available.")
        return definition

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": definition.name,
                "description": definition.description,
                "read_only": definition.read_only,
                "parameters": definition.arguments_model.model_json_schema(),
            }
            for definition in self._tools.values()
        ]

    def openai_tool_schemas(self) -> list[dict[str, Any]]:
        """Convert registered tools to OpenAI-compatible function schemas."""
        return [
            {
                "type": "function",
                "function": {
                    "name": definition.name,
                    "description": definition.description,
                    "parameters": definition.arguments_model.model_json_schema(),
                },
            }
            for definition in self._tools.values()
        ]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: AgentToolContext,
    ) -> dict[str, Any]:
        definition = self.get(name)
        try:
            validated = definition.arguments_model.model_validate(arguments)
        except ValidationError as exc:
            raise AgentToolError("Tool arguments did not match the registered schema.") from exc
        if context.repository.user_id != context.user_id:
            raise AgentToolError("Saved repository was not found.")
        try:
            result = await definition.handler(context, validated)
        except AgentToolError:
            raise
        except Exception as exc:
            # Do not expose database/provider exception contents or secrets to the model/API.
            raise AgentToolError(f"Tool '{name}' could not complete its read-only operation.") from exc
        if not isinstance(result, dict):
            raise AgentToolError("The tool returned an invalid result.")
        return result


def build_agent_tool_registry() -> AgentToolRegistry:
    """Build the fixed Phase 2 tool allowlist."""
    from app.agents.tools.repository_tools import (
        InspectSourceArguments,
        ListIndexedFilesArguments,
        RepositoryOverviewArguments,
        SearchCodeArguments,
        inspect_source,
        list_indexed_files,
        repository_overview,
        search_code,
    )

    registry = AgentToolRegistry()
    registry.register(
        AgentToolDefinition(
            name="repository_overview",
            description="Return safe metadata and indexing statistics for the selected repository snapshot.",
            arguments_model=RepositoryOverviewArguments,
            handler=repository_overview,
        )
    )
    registry.register(
        AgentToolDefinition(
            name="list_indexed_files",
            description="List paths and line/chunk statistics for files in the selected indexed commit.",
            arguments_model=ListIndexedFilesArguments,
            handler=list_indexed_files,
        )
    )
    registry.register(
        AgentToolDefinition(
            name="search_code",
            description="Search the selected repository snapshot and return relevant source excerpts with citations.",
            arguments_model=SearchCodeArguments,
            handler=search_code,
        )
    )
    registry.register(
        AgentToolDefinition(
            name="inspect_source",
            description="Read bounded line ranges from one exact file in the selected indexed repository snapshot.",
            arguments_model=InspectSourceArguments,
            handler=inspect_source,
        )
    )
    return registry
