import argparse
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app


def main() -> int:
    parser = argparse.ArgumentParser(description="Run API smoke tests with FastAPI TestClient.")
    parser.add_argument("--strict-ready", action="store_true", help="Require /health/ready to return 200.")
    args = parser.parse_args()

    failures: list[str] = []
    drone_question = (
        "\u660e\u5929\u4e0a\u5348 9 \u70b9\u8ba9\u4e24\u67b6\u65e0\u4eba\u673a"
        "\u5de1\u68c0 A \u533a\u57df\u7684\u8f93\u7535\u7ebf\u8def\uff0c"
        "\u91cd\u70b9\u68c0\u67e5\u6746\u5854\u548c\u7591\u4f3c\u5f02\u7269\u3002"
    )
    with TestClient(app) as client:
        checks = [
            ("GET /health/live", lambda: client.get("/health/live"), 200),
            ("GET /app/", lambda: client.get("/app/"), 200),
            ("GET /app/app.js", lambda: client.get("/app/app.js"), 200),
            ("GET /eval/dataset", lambda: client.get("/eval/dataset"), 200),
            ("GET /skills", lambda: client.get("/skills"), 200),
            ("GET /mcp/servers", lambda: client.get("/mcp/servers"), 200),
            ("GET /workflows", lambda: client.get("/workflows"), 200),
            (
                "POST /skills/drone_mission_planner/run",
                lambda: client.post(
                    "/skills/drone_mission_planner/run",
                    json={"question": drone_question, "session_id": "smoke_drone"},
                ),
                200,
            ),
        ]
        if args.strict_ready:
            checks.append(("GET /health/ready", lambda: client.get("/health/ready"), 200))

        for name, call, expected in checks:
            response = call()
            print(f"{name} -> {response.status_code}")
            if response.status_code != expected:
                failures.append(f"{name} expected {expected}, got {response.status_code}: {response.text[:300]}")
                continue
            if name == "POST /skills/drone_mission_planner/run":
                payload = response.json()
                answer = payload.get("answer", "")
                tool_names = [item.get("name") for item in payload.get("tool_calls", [])]
                if payload.get("workflow_id") != "drone_mission_planning_v1":
                    failures.append("drone smoke used unexpected workflow_id")
                if "powerline_inspection" not in answer or "parallel_area_split" not in answer:
                    failures.append("drone smoke answer did not include expected mission plan markers")
                if "drone_mission_export" not in tool_names:
                    failures.append("drone smoke did not execute mission export tool")

    if failures:
        print("smoke failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
