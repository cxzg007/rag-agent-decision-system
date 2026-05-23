import time
import asyncio

from elasticsearch import AsyncElasticsearch
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.schemas.health import DependencyHealth, HealthResponse
from app.services.memory import session_memory


class HealthService:
    async def check(self) -> HealthResponse:
        dependencies = {
            "api": DependencyHealth(status="ok", detail="service is running", latency_ms=0.0),
            "elasticsearch": await self._check_elasticsearch(),
            "redis": await self._check_redis(),
            "postgresql": self._check_postgresql(),
        }
        overall = "ok" if all(item.status == "ok" for item in dependencies.values()) else "degraded"
        return HealthResponse(status=overall, app_env=settings.app_env, dependencies=dependencies)

    async def ready(self) -> HealthResponse:
        return await self.check()

    def live(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            app_env=settings.app_env,
            dependencies={"api": DependencyHealth(status="ok", detail="process is alive", latency_ms=0.0)},
        )

    async def _check_elasticsearch(self) -> DependencyHealth:
        started = time.perf_counter()
        client = AsyncElasticsearch(settings.elasticsearch_url, request_timeout=settings.dependency_check_timeout_seconds)
        try:
            response = await client.cluster.health()
            latency_ms = (time.perf_counter() - started) * 1000
            return DependencyHealth(
                status="ok",
                detail=f"cluster={response.get('status')}",
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            return DependencyHealth(status="down", detail=str(exc), latency_ms=latency_ms)
        finally:
            await client.close()

    async def _check_redis(self) -> DependencyHealth:
        started = time.perf_counter()
        try:
            ok = await asyncio.wait_for(
                session_memory.client.ping(),
                timeout=settings.dependency_check_timeout_seconds,
            )
            latency_ms = (time.perf_counter() - started) * 1000
            return DependencyHealth(status="ok" if ok else "down", detail="PING", latency_ms=latency_ms)
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            return DependencyHealth(status="down", detail=str(exc), latency_ms=latency_ms)

    def _check_postgresql(self) -> DependencyHealth:
        started = time.perf_counter()
        try:
            with engine.connect() as conn:
                conn.execute(text("select 1")).scalar()
            latency_ms = (time.perf_counter() - started) * 1000
            return DependencyHealth(status="ok", detail="select 1", latency_ms=latency_ms)
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            return DependencyHealth(status="down", detail=str(exc), latency_ms=latency_ms)


health_service = HealthService()
