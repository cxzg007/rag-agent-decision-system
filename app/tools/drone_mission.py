import math
import re
from typing import Literal

from pydantic import BaseModel, Field


class DroneMissionParseInput(BaseModel):
    request: str


class DroneMissionParseOutput(BaseModel):
    mission_type: str
    area_id: str
    drone_count: int = Field(ge=1, le=8)
    targets: list[str]
    time_window: str
    priority: Literal["low", "normal", "high"] = "normal"
    constraints: list[str] = []


class DroneMapQueryInput(BaseModel):
    area_id: str
    mission_type: str


class DroneMapQueryOutput(BaseModel):
    area_id: str
    center: dict[str, float]
    boundary: list[dict[str, float]]
    launch_site: dict[str, float]
    landing_site: dict[str, float]
    obstacles: list[dict]
    corridor_width_m: int


class DroneNoFlyZoneInput(BaseModel):
    area_id: str
    boundary: list[dict[str, float]]


class DroneNoFlyZoneOutput(BaseModel):
    restricted_zones: list[dict]
    has_conflict: bool
    notes: list[str]


class DroneWeatherInput(BaseModel):
    area_id: str
    time_window: str


class DroneWeatherOutput(BaseModel):
    wind_speed_mps: float
    gust_mps: float
    visibility_km: float
    precipitation: str
    flyable: bool
    notes: list[str]


class DroneRoutePlanInput(BaseModel):
    mission: DroneMissionParseOutput
    map_context: DroneMapQueryOutput
    no_fly: DroneNoFlyZoneOutput
    weather: DroneWeatherOutput


class DroneRoutePlanOutput(BaseModel):
    routes: list[dict]
    total_distance_km: float
    route_strategy: str


class DroneRiskAssessmentInput(BaseModel):
    mission: DroneMissionParseOutput
    route_plan: DroneRoutePlanOutput
    no_fly: DroneNoFlyZoneOutput
    weather: DroneWeatherOutput


class DroneRiskAssessmentOutput(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    approval_required: bool
    risks: list[dict]
    mitigations: list[str]


class DroneMissionExportInput(BaseModel):
    mission: DroneMissionParseOutput
    route_plan: DroneRoutePlanOutput
    risk_assessment: DroneRiskAssessmentOutput


class DroneMissionExportOutput(BaseModel):
    mission_plan: dict
    markdown: str


async def drone_mission_parse(payload: DroneMissionParseInput) -> DroneMissionParseOutput:
    text = payload.request
    lower = text.lower()
    area_id = _extract_area_id(text)
    drone_count = _extract_drone_count(text)
    mission_type = "general_survey"
    if any(term in text for term in ["输电", "电力", "杆塔", "线路"]):
        mission_type = "powerline_inspection"
    elif any(term in text for term in ["搜救", "搜索", "救援"]):
        mission_type = "search_and_rescue"
    elif any(term in text for term in ["巡逻", "安防", "边界"]):
        mission_type = "security_patrol"

    targets = []
    target_rules = {
        "tower": ["杆塔", "塔"],
        "foreign_object": ["异物", "悬挂物"],
        "thermal_anomaly": ["红外", "发热", "热异常"],
        "person": ["人员", "行人", "失踪"],
        "vehicle": ["车辆", "车"],
        "boundary": ["边界", "围栏"],
    }
    for target, keywords in target_rules.items():
        if any(keyword in text for keyword in keywords):
            targets.append(target)
    if not targets:
        targets = ["visual_inspection"]

    constraints = []
    if "低空" in text:
        constraints.append("prefer_low_altitude")
    if "避开" in text or "绕开" in text:
        constraints.append("avoid_sensitive_area")
    if "夜间" in text or "晚上" in text or "night" in lower:
        constraints.append("night_operation")

    return DroneMissionParseOutput(
        mission_type=mission_type,
        area_id=area_id,
        drone_count=drone_count,
        targets=targets,
        time_window=_extract_time_window(text),
        priority="high" if any(term in text for term in ["紧急", "立即", "高优先级"]) else "normal",
        constraints=constraints,
    )


async def drone_map_query(payload: DroneMapQueryInput) -> DroneMapQueryOutput:
    catalog = _area_catalog()
    area = catalog.get(payload.area_id, catalog["A"])
    return DroneMapQueryOutput(
        area_id=payload.area_id,
        center=area["center"],
        boundary=area["boundary"],
        launch_site=area["launch_site"],
        landing_site=area["landing_site"],
        obstacles=area["obstacles"],
        corridor_width_m=80 if payload.mission_type == "powerline_inspection" else 120,
    )


async def drone_no_fly_zone(payload: DroneNoFlyZoneInput) -> DroneNoFlyZoneOutput:
    zones = [
        {"zone_id": "NFZ-001", "name": "机场净空保护区", "area_id": "C", "severity": "high"},
        {"zone_id": "NFZ-002", "name": "临时活动管制区", "area_id": "B", "severity": "medium"},
    ]
    conflicts = [zone for zone in zones if zone["area_id"].lower() == payload.area_id.lower()]
    notes = ["未发现禁飞区冲突"] if not conflicts else [f"航线区域与 {item['name']} 存在冲突" for item in conflicts]
    return DroneNoFlyZoneOutput(restricted_zones=conflicts, has_conflict=bool(conflicts), notes=notes)


async def drone_weather(payload: DroneWeatherInput) -> DroneWeatherOutput:
    wind = 4.8
    gust = 7.2
    precipitation = "none"
    notes = ["天气适合常规巡检"]
    if "夜间" in payload.time_window:
        notes.append("夜间任务需要开启避障灯和红外载荷")
    if payload.area_id.upper() == "B":
        wind = 6.5
        gust = 9.8
        notes.append("B 区域阵风偏高，建议降低速度并预留返航电量")
    flyable = wind <= 8.0 and gust <= 12.0 and precipitation != "heavy"
    return DroneWeatherOutput(
        wind_speed_mps=wind,
        gust_mps=gust,
        visibility_km=8.0,
        precipitation=precipitation,
        flyable=flyable,
        notes=notes,
    )


async def drone_route_plan(payload: DroneRoutePlanInput) -> DroneRoutePlanOutput:
    mission = payload.mission
    area = payload.map_context
    routes = []
    segments = _split_boundary(area.boundary, mission.drone_count)
    for index in range(mission.drone_count):
        waypoints = [area.launch_site, *segments[index], area.landing_site]
        distance = _route_distance_km(waypoints)
        routes.append(
            {
                "drone_id": f"UAV-{index + 1:02d}",
                "altitude_m": 80 if mission.mission_type == "powerline_inspection" else 100,
                "speed_mps": 8 if payload.weather.wind_speed_mps <= 5 else 6,
                "payload": _payload_for_targets(mission.targets),
                "waypoints": waypoints,
                "distance_km": round(distance, 2),
                "estimated_minutes": round((distance * 1000) / max(1, 8 if payload.weather.wind_speed_mps <= 5 else 6) / 60, 1),
                "actions": _actions_for_targets(mission.targets),
            }
        )
    strategy = "parallel_area_split" if mission.drone_count > 1 else "single_route_survey"
    if payload.no_fly.has_conflict:
        strategy += "_requires_manual_reroute"
    return DroneRoutePlanOutput(
        routes=routes,
        total_distance_km=round(sum(item["distance_km"] for item in routes), 2),
        route_strategy=strategy,
    )


async def drone_risk_assessment(payload: DroneRiskAssessmentInput) -> DroneRiskAssessmentOutput:
    risks = []
    mitigations = []
    if payload.no_fly.has_conflict:
        risks.append({"level": "high", "type": "no_fly_zone", "detail": "; ".join(payload.no_fly.notes)})
        mitigations.append("必须人工重规划航线并确认避开禁飞区")
    if not payload.weather.flyable:
        risks.append({"level": "high", "type": "weather", "detail": "当前天气不满足安全飞行阈值"})
        mitigations.append("推迟任务或降低任务范围")
    elif payload.weather.gust_mps >= 9:
        risks.append({"level": "medium", "type": "wind", "detail": "阵风偏高，影响航线稳定性"})
        mitigations.append("降低速度，增加返航电量冗余")

    longest = max((item["distance_km"] for item in payload.route_plan.routes), default=0)
    if longest > 8:
        risks.append({"level": "medium", "type": "battery", "detail": f"最长单机航程 {longest:.2f} km"})
        mitigations.append("设置中途返航点或更换高续航电池")

    if "night_operation" in payload.mission.constraints:
        risks.append({"level": "medium", "type": "night_operation", "detail": "夜间任务对视觉避障和人工观察要求更高"})
        mitigations.append("启用夜航灯、红外载荷，并安排地面观察员")

    high = any(item["level"] == "high" for item in risks)
    medium = any(item["level"] == "medium" for item in risks)
    risk_level = "high" if high else "medium" if medium else "low"
    if not mitigations:
        mitigations.append("按标准作业流程执行，起飞前完成设备自检")
    return DroneRiskAssessmentOutput(
        risk_level=risk_level,
        approval_required=True,
        risks=risks or [{"level": "low", "type": "standard", "detail": "未发现阻断性风险"}],
        mitigations=mitigations,
    )


async def drone_mission_export(payload: DroneMissionExportInput) -> DroneMissionExportOutput:
    mission = payload.mission
    route_plan = payload.route_plan
    risk = payload.risk_assessment
    mission_plan = {
        "mission_type": mission.mission_type,
        "area_id": mission.area_id,
        "time_window": mission.time_window,
        "approval_required": risk.approval_required,
        "risk_level": risk.risk_level,
        "routes": route_plan.routes,
        "mitigations": risk.mitigations,
        "export_format": "review_only_json",
    }
    lines = [
        "# 无人机任务规划方案",
        "",
        f"- 任务类型: {mission.mission_type}",
        f"- 作业区域: {mission.area_id}",
        f"- 无人机数量: {mission.drone_count}",
        f"- 目标: {', '.join(mission.targets)}",
        f"- 时间窗口: {mission.time_window}",
        f"- 航线策略: {route_plan.route_strategy}",
        f"- 总航程: {route_plan.total_distance_km:.2f} km",
        f"- 风险等级: {risk.risk_level}",
        f"- 是否需要人工审批: {'是' if risk.approval_required else '否'}",
        "",
        "## 航线分配",
    ]
    for route in route_plan.routes:
        lines.append(
            f"- {route['drone_id']}: {route['distance_km']} km, {route['estimated_minutes']} 分钟, "
            f"{route['altitude_m']} m, {route['speed_mps']} m/s, 载荷={', '.join(route['payload'])}"
        )
    lines.extend(["", "## 风险与缓解措施"])
    for item in risk.risks:
        lines.append(f"- [{item['level']}] {item['type']}: {item['detail']}")
    for item in risk.mitigations:
        lines.append(f"- 缓解: {item}")
    lines.extend(
        [
            "",
            "## 安全边界",
            "- 当前结果仅用于任务规划和人工审批，不会直接下发飞控命令。",
            "- 下发前必须由持证操作员确认禁飞区、天气、电量和现场安全条件。",
        ]
    )
    return DroneMissionExportOutput(mission_plan=mission_plan, markdown="\n".join(lines))


def _extract_area_id(text: str) -> str:
    match = re.search(r"([A-Za-z])\s*区", text)
    return match.group(1).upper() if match else "A"


def _extract_drone_count(text: str) -> int:
    zh_digits = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5}
    match = re.search(r"(\d+)\s*架", text)
    if match:
        return max(1, min(int(match.group(1)), 8))
    for char, value in zh_digits.items():
        if f"{char}架" in text:
            return value
    return 1


def _extract_time_window(text: str) -> str:
    if "明天" in text and "上午" in text:
        return "明天上午"
    if "明天" in text and "下午" in text:
        return "明天下午"
    if "夜间" in text or "晚上" in text:
        return "夜间"
    if "立即" in text or "现在" in text:
        return "immediate"
    return "待确认"


def _area_catalog() -> dict[str, dict]:
    return {
        "A": {
            "center": {"lat": 31.2304, "lon": 121.4737},
            "launch_site": {"lat": 31.226, "lon": 121.466},
            "landing_site": {"lat": 31.226, "lon": 121.466},
            "boundary": [
                {"lat": 31.226, "lon": 121.466},
                {"lat": 31.236, "lon": 121.468},
                {"lat": 31.239, "lon": 121.482},
                {"lat": 31.228, "lon": 121.486},
            ],
            "obstacles": [
                {"type": "powerline", "height_m": 45, "note": "输电线路走廊"},
                {"type": "building", "height_m": 65, "note": "区域东侧建筑群"},
            ],
        },
        "B": {
            "center": {"lat": 31.18, "lon": 121.52},
            "launch_site": {"lat": 31.176, "lon": 121.512},
            "landing_site": {"lat": 31.176, "lon": 121.512},
            "boundary": [
                {"lat": 31.176, "lon": 121.512},
                {"lat": 31.189, "lon": 121.516},
                {"lat": 31.188, "lon": 121.532},
                {"lat": 31.177, "lon": 121.529},
            ],
            "obstacles": [{"type": "temporary_crane", "height_m": 75, "note": "施工吊装设备"}],
        },
    }


def _split_boundary(boundary: list[dict[str, float]], drone_count: int) -> list[list[dict[str, float]]]:
    segments = [[] for _ in range(drone_count)]
    for index, point in enumerate(boundary):
        segments[index % drone_count].append(point)
    return segments


def _route_distance_km(points: list[dict[str, float]]) -> float:
    return sum(_distance_km(points[index], points[index + 1]) for index in range(len(points) - 1))


def _distance_km(a: dict[str, float], b: dict[str, float]) -> float:
    lat_km = (b["lat"] - a["lat"]) * 111.0
    lon_km = (b["lon"] - a["lon"]) * 111.0 * math.cos(math.radians((a["lat"] + b["lat"]) / 2))
    return math.sqrt(lat_km * lat_km + lon_km * lon_km)


def _payload_for_targets(targets: list[str]) -> list[str]:
    payloads = ["visible_camera"]
    if any(target in targets for target in ["thermal_anomaly", "person"]):
        payloads.append("infrared_camera")
    if "tower" in targets or "foreign_object" in targets:
        payloads.append("zoom_camera")
    return payloads


def _actions_for_targets(targets: list[str]) -> list[str]:
    actions = ["capture_overview_video"]
    if "tower" in targets:
        actions.append("capture_tower_closeups")
    if "foreign_object" in targets:
        actions.append("mark_suspected_foreign_object")
    if "person" in targets:
        actions.append("thermal_scan")
    return actions
