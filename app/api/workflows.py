import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.security import require_api_key
from app.schemas.workflow import WorkflowDefinitionSummary, WorkflowRequest, WorkflowResponse
from app.services.trace_store import trace_store
from app.services.workflow import workflow_service
from app.services.workflow.definition import list_workflow_definitions, reload_workflow_definitions

router = APIRouter()


@router.get("", response_model=list[WorkflowDefinitionSummary])
async def list_workflows() -> list[WorkflowDefinitionSummary]:
    return [
        WorkflowDefinitionSummary(
            workflow_id=item.workflow_id,
            node_count=len(item.nodes),
            edge_count=len(item.edges),
            max_iterations=item.max_iterations,
            node_ids=[node.node_id for node in item.nodes],
        )
        for item in list_workflow_definitions()
    ]


@router.post("/reload", response_model=list[WorkflowDefinitionSummary], dependencies=[Depends(require_api_key)])
async def reload_workflows() -> list[WorkflowDefinitionSummary]:
    return [
        WorkflowDefinitionSummary(
            workflow_id=item.workflow_id,
            node_count=len(item.nodes),
            edge_count=len(item.edges),
            max_iterations=item.max_iterations,
            node_ids=[node.node_id for node in item.nodes],
        )
        for item in reload_workflow_definitions().values()
    ]


@router.post("/run", response_model=WorkflowResponse)
async def run_workflow(request: WorkflowRequest) -> WorkflowResponse:
    try:
        return await workflow_service.run(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/stream")
async def stream_workflow(request: WorkflowRequest) -> StreamingResponse:
    async def event_stream():
        async for event in workflow_service.stream(request):
            yield f"event: {event.type}\n"
            yield f"data: {json.dumps(event.payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{workflow_run_id}", dependencies=[Depends(require_api_key)])
async def get_workflow_run(workflow_run_id: str):
    run = trace_store.get_workflow_run(workflow_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="workflow run not found")
    return run
