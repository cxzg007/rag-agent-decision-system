from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_api_key
from app.schemas.skill import MCPServerDefinition, MCPToolCallRequest, MCPToolCallResponse, RegistryReloadResponse
from app.services.mcp_client import MCPExecutionError, mcp_client
from app.services.skill_registry import (
    get_mcp_server_definition,
    load_mcp_server_definitions,
    load_skill_definitions,
    reload_skill_and_mcp_registries,
    validate_skill_links,
)

router = APIRouter()


@router.get("/servers", response_model=list[MCPServerDefinition])
async def list_mcp_servers() -> list[MCPServerDefinition]:
    return list(load_mcp_server_definitions().values())


@router.get("/servers/{server_id}", response_model=MCPServerDefinition)
async def get_mcp_server(server_id: str) -> MCPServerDefinition:
    try:
        return get_mcp_server_definition(server_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/servers/{server_id}/tools/{tool_name}/call",
    response_model=MCPToolCallResponse,
    dependencies=[Depends(require_api_key)],
)
async def call_mcp_tool(server_id: str, tool_name: str, request: MCPToolCallRequest) -> MCPToolCallResponse:
    try:
        server = get_mcp_server_definition(server_id)
        result = await mcp_client.call_tool(server, tool_name, request.arguments)
        return MCPToolCallResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MCPExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/reload", response_model=RegistryReloadResponse, dependencies=[Depends(require_api_key)])
async def reload_mcp_servers() -> RegistryReloadResponse:
    skills, mcp_servers = reload_skill_and_mcp_registries()
    errors = validate_skill_links()
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    return RegistryReloadResponse(skills=len(skills), mcp_servers=len(mcp_servers))
