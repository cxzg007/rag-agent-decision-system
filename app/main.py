from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import chat, documents, eval, feedback, health, mcp, memory, skills, traces, workflows
from app.core.config import settings
from app.core.lifespan import lifespan
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="RAG-enhanced Agent decision system scaffold.",
        lifespan=lifespan,
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(documents.router, prefix="/documents", tags=["documents"])
    app.include_router(chat.router, prefix="/chat", tags=["chat"])
    app.include_router(eval.router, prefix="/eval", tags=["eval"])
    app.include_router(traces.router, prefix="/traces", tags=["traces"])
    app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(memory.router, prefix="/memory", tags=["memory"])
    app.include_router(skills.router, prefix="/skills", tags=["skills"])
    app.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
    app.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
    app.mount("/app", StaticFiles(directory="app/static", html=True), name="dashboard")

    @app.get("/", include_in_schema=False)
    async def dashboard_redirect() -> RedirectResponse:
        return RedirectResponse(url="/app/")

    return app


app = create_app()
