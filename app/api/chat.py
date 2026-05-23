import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.agent import agent_service

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await agent_service.run(request)


@router.post("/stream")
async def stream_chat(request: ChatRequest) -> StreamingResponse:
    async def event_stream():
        async for event in agent_service.stream(request):
            yield f"event: {event.type}\n"
            yield f"data: {json.dumps(event.payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
