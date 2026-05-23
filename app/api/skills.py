import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.security import require_api_key
from app.schemas.skill import RegistryReloadResponse, SkillDefinition, SkillRunRequest, SkillSummary
from app.schemas.workflow import WorkflowRequest, WorkflowResponse
from app.services.skill_registry import (
    get_skill_definition,
    load_mcp_server_definitions,
    load_skill_definitions,
    reload_skill_and_mcp_registries,
    validate_skill_links,
)
from app.services.workflow import workflow_service
from app.services.workflow.definition import get_workflow_definition

router = APIRouter()


@router.get("", response_model=list[SkillSummary])
async def list_skills() -> list[SkillSummary]:
    return [
        SkillSummary(
            skill_id=item.skill_id,
            name=item.name,
            version=item.version,
            description=item.description,
            skill_path=item.skill_path,
            workflow_id=item.workflow_id,
            enabled=item.enabled,
            tags=item.tags,
        )
        for item in load_skill_definitions().values()
    ]


@router.get("/{skill_id}", response_model=SkillDefinition)
async def get_skill(skill_id: str) -> SkillDefinition:
    try:
        return get_skill_definition(skill_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{skill_id}/run", response_model=WorkflowResponse, dependencies=[Depends(require_api_key)])
async def run_skill(skill_id: str, request: SkillRunRequest) -> WorkflowResponse:
    skill = _get_enabled_skill(skill_id)
    workflow_request = _to_workflow_request(skill, request)
    try:
        return await workflow_service.run(workflow_request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{skill_id}/stream", dependencies=[Depends(require_api_key)])
async def stream_skill(skill_id: str, request: SkillRunRequest) -> StreamingResponse:
    skill = _get_enabled_skill(skill_id)
    workflow_request = _to_workflow_request(skill, request)

    async def event_stream():
        async for event in workflow_service.stream(workflow_request):
            yield f"event: {event.type}\n"
            yield f"data: {json.dumps(event.payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/reload", response_model=RegistryReloadResponse, dependencies=[Depends(require_api_key)])
async def reload_skills() -> RegistryReloadResponse:
    skills, mcp_servers = reload_skill_and_mcp_registries()
    errors = validate_skill_links()
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    return RegistryReloadResponse(skills=len(skills), mcp_servers=len(mcp_servers))


def _get_enabled_skill(skill_id: str) -> SkillDefinition:
    try:
        skill = get_skill_definition(skill_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not skill.enabled:
        raise HTTPException(status_code=403, detail=f"skill is disabled: {skill_id}")
    try:
        get_workflow_definition(skill.workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return skill


def _to_workflow_request(skill: SkillDefinition, request: SkillRunRequest) -> WorkflowRequest:
    merged = dict(skill.default_inputs)
    merged.update(request.inputs)
    allowed = {
        "top_k",
        "use_llm_planner",
        "use_llm_critic",
        "use_llm_answer",
    }
    workflow_inputs = {key: value for key, value in merged.items() if key in allowed}
    return WorkflowRequest(
        question=request.question,
        session_id=request.session_id,
        workflow_id=skill.workflow_id,
        **workflow_inputs,
    )
