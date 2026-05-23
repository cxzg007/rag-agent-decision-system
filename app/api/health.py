from fastapi import APIRouter, HTTPException

from app.schemas.health import HealthResponse
from app.services.health import health_service

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def health() -> HealthResponse:
    return await health_service.check()


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return health_service.live()


@router.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    response = await health_service.ready()
    if response.status != "ok":
        raise HTTPException(status_code=503, detail=response.model_dump())
    return response
