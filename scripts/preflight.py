import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.health import health_service
from app.services.skill_registry import load_mcp_server_definitions, load_skill_definitions, validate_skill_links
from app.services.workflow.definition import list_workflow_definitions
from app.services.retriever import retriever
from app.services.memory import session_memory


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run production preflight checks.")
    parser.add_argument("--strict-deps", action="store_true", help="Fail when ES/Redis/PostgreSQL are unavailable.")
    args = parser.parse_args()

    failures: list[str] = []
    skills = load_skill_definitions()
    mcp_servers = load_mcp_server_definitions()
    workflows = list_workflow_definitions()
    link_errors = validate_skill_links()

    if not skills:
        failures.append("no skill definitions loaded")
    if not mcp_servers:
        failures.append("no MCP server definitions loaded")
    if not workflows:
        failures.append("no workflow definitions loaded")
    failures.extend(link_errors)

    health = await health_service.check()
    if args.strict_deps:
        for name, item in health.dependencies.items():
            if item.status != "ok":
                failures.append(f"dependency {name} is {item.status}: {item.detail}")

    print(f"skills={len(skills)} mcp_servers={len(mcp_servers)} workflows={len(workflows)} health={health.status}")
    for name, item in health.dependencies.items():
        print(f"{name}: {item.status} {item.latency_ms or 0:.2f}ms {item.detail or ''}")

    await retriever.close()
    await session_memory.close()

    if failures:
        print("preflight failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
