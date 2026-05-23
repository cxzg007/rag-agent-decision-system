from typing import Any, Literal

from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    skill_id: str
    name: str
    version: str = "0.1.0"
    description: str
    skill_path: str | None = None
    instructions_path: str | None = None
    workflow_id: str
    default_inputs: dict[str, Any] = Field(default_factory=dict)
    allowed_tool_scopes: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


class SkillSummary(BaseModel):
    skill_id: str
    name: str
    version: str
    description: str
    skill_path: str | None = None
    workflow_id: str
    enabled: bool
    tags: list[str] = Field(default_factory=list)


class SkillRunRequest(BaseModel):
    question: str
    session_id: str = "default"
    inputs: dict[str, Any] = Field(default_factory=dict)


class MCPToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    scope: str = "external"


class MCPServerDefinition(BaseModel):
    server_id: str
    name: str
    transport: Literal["internal", "stdio", "http", "sse"] = "stdio"
    enabled: bool = False
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = 30.0
    allowed_tool_scopes: list[str] = Field(default_factory=list)
    tools: list[MCPToolDefinition] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegistryReloadResponse(BaseModel):
    skills: int
    mcp_servers: int


class MCPToolCallRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class MCPToolCallResponse(BaseModel):
    server_id: str
    tool_name: str
    transport: str
    result: Any
    latency_ms: float
