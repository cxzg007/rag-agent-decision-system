import asyncio
import logging

from app.services.dependency_caller import dependency_caller


def test_dependency_caller_retries_and_propagates_trace_id(caplog):
    attempts = {"count": 0}

    async def flaky():
        attempts["count"] += 1
        assert dependency_caller.current_trace_id() == "trace-test"
        if attempts["count"] == 1:
            raise RuntimeError("temporary failure")
        return "ok"

    with caplog.at_level(logging.INFO, logger="app.dependency"):
        result = asyncio.run(
            dependency_caller.call(
                name="unit.flaky",
                dependency_type="unit",
                func=flaky,
                timeout_seconds=1,
                retry_count=1,
                trace_id="trace-test",
            )
        )

    assert result == "ok"
    assert attempts["count"] == 2
    assert dependency_caller.current_trace_id() is None
    assert "external_dependency_call_failed" in caplog.text
    assert "external_dependency_call_success" in caplog.text
    assert "trace-test" in caplog.text


def test_dependency_caller_uses_fallback_after_failure(caplog):
    async def broken():
        raise ValueError("dependency unavailable")

    with caplog.at_level(logging.INFO, logger="app.dependency"):
        result = asyncio.run(
            dependency_caller.call(
                name="unit.broken",
                dependency_type="unit",
                func=broken,
                timeout_seconds=1,
                retry_count=0,
                fallback={"status": "fallback"},
                trace_id="trace-fallback",
            )
        )

    assert result == {"status": "fallback"}
    assert "external_dependency_fallback_used" in caplog.text
    assert "dependency unavailable" in caplog.text
