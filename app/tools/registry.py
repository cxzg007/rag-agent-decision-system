from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.tools.knowledge_search import KnowledgeSearchInput, knowledge_search
from app.tools.memory_read import MemoryReadInput, memory_read
from app.tools.parent_context import ParentContextInput, parent_context
from app.tools.plan_generator import PlanGeneratorInput, plan_generator
from app.tools.web_search import WebSearchInput, web_search
from app.tools.drone_mission import (
    DroneMapQueryInput,
    DroneMissionExportInput,
    DroneMissionParseInput,
    DroneNoFlyZoneInput,
    DroneRiskAssessmentInput,
    DroneRoutePlanInput,
    DroneWeatherInput,
    drone_map_query,
    drone_mission_export,
    drone_mission_parse,
    drone_no_fly_zone,
    drone_risk_assessment,
    drone_route_plan,
    drone_weather,
)


ToolHandler = Callable[[Any], Awaitable[object]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: ToolHandler
    timeout_seconds: float = 30.0
    retry_count: int = 0
    scope: str = "default"


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "knowledge_search": ToolSpec(
        name="knowledge_search",
        description="Search the indexed knowledge base using BM25/vector/hybrid retrieval and optional rerank.",
        input_model=KnowledgeSearchInput,
        handler=knowledge_search,
        timeout_seconds=90.0,
        retry_count=0,
        scope="retrieval",
    ),
    "parent_context": ToolSpec(
        name="parent_context",
        description="Fetch parent chunk context for retrieved child chunks.",
        input_model=ParentContextInput,
        handler=parent_context,
        timeout_seconds=15.0,
        retry_count=1,
        scope="retrieval",
    ),
    "memory_read": ToolSpec(
        name="memory_read",
        description="Read recent session-level memory from Redis.",
        input_model=MemoryReadInput,
        handler=memory_read,
        timeout_seconds=5.0,
        retry_count=0,
        scope="memory",
    ),
    "web_search": ToolSpec(
        name="web_search",
        description="Placeholder web search tool.",
        input_model=WebSearchInput,
        handler=web_search,
        timeout_seconds=10.0,
        retry_count=0,
        scope="external",
    ),
    "plan_generator": ToolSpec(
        name="plan_generator",
        description="Generate a deterministic task plan from evidence.",
        input_model=PlanGeneratorInput,
        handler=plan_generator,
        timeout_seconds=10.0,
        retry_count=0,
        scope="planning",
    ),
    "drone_mission_parse": ToolSpec(
        name="drone_mission_parse",
        description="Parse a natural-language drone mission request into structured mission intent.",
        input_model=DroneMissionParseInput,
        handler=drone_mission_parse,
        timeout_seconds=5.0,
        retry_count=0,
        scope="mission",
    ),
    "drone_map_query": ToolSpec(
        name="drone_map_query",
        description="Return deterministic demo map context for a drone operating area.",
        input_model=DroneMapQueryInput,
        handler=drone_map_query,
        timeout_seconds=5.0,
        retry_count=0,
        scope="mission",
    ),
    "drone_no_fly_zone": ToolSpec(
        name="drone_no_fly_zone",
        description="Check demo no-fly-zone conflicts for a drone mission area.",
        input_model=DroneNoFlyZoneInput,
        handler=drone_no_fly_zone,
        timeout_seconds=5.0,
        retry_count=0,
        scope="mission",
    ),
    "drone_weather": ToolSpec(
        name="drone_weather",
        description="Return deterministic demo weather constraints for a drone mission.",
        input_model=DroneWeatherInput,
        handler=drone_weather,
        timeout_seconds=5.0,
        retry_count=0,
        scope="mission",
    ),
    "drone_route_plan": ToolSpec(
        name="drone_route_plan",
        description="Generate candidate drone routes from mission, map, no-fly-zone, and weather context.",
        input_model=DroneRoutePlanInput,
        handler=drone_route_plan,
        timeout_seconds=10.0,
        retry_count=0,
        scope="mission",
    ),
    "drone_risk_assessment": ToolSpec(
        name="drone_risk_assessment",
        description="Assess drone mission risks and produce mitigations.",
        input_model=DroneRiskAssessmentInput,
        handler=drone_risk_assessment,
        timeout_seconds=10.0,
        retry_count=0,
        scope="mission",
    ),
    "drone_mission_export": ToolSpec(
        name="drone_mission_export",
        description="Export a review-only drone mission plan and human-readable approval summary.",
        input_model=DroneMissionExportInput,
        handler=drone_mission_export,
        timeout_seconds=10.0,
        retry_count=0,
        scope="mission",
    ),
}


def get_tool_spec(name: str) -> ToolSpec:
    try:
        return TOOL_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"unknown tool: {name}") from exc
