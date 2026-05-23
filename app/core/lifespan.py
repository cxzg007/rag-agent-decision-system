from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.session import engine
from app.services.memory import session_memory
from app.services.retriever import retriever


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await close_app_resources()


async def close_app_resources() -> None:
    await retriever.close()
    await session_memory.close()
    engine.dispose()
