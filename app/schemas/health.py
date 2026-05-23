from pydantic import BaseModel, Field


class DependencyHealth(BaseModel):
    status: str
    detail: str | None = None
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    status: str
    app_env: str | None = None
    dependencies: dict[str, DependencyHealth] = Field(default_factory=dict)
