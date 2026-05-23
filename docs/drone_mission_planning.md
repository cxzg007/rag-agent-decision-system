# 无人机任务规划业务方案

## 目标

将自然语言无人机作业需求转成可人工审批的任务计划。当前实现是 deterministic MVP，不依赖 LLM，也不会下发真实飞控命令。

## 入口

Skill:

```text
drone_mission_planner
```

Workflow:

```text
drone_mission_planning_v1
```

示例请求：

```text
明天上午 9 点让两架无人机巡检 A 区域的输电线路，重点检查杆塔和疑似异物。
```

## Workflow

```text
mission_parse
  -> mission_context
  -> mission_route_plan
  -> mission_risk_review
  -> mission_export
```

## Tools

```text
drone_mission_parse     -> 任务解析
drone_map_query         -> 地图上下文、起降点、障碍物
drone_no_fly_zone       -> 禁飞区/临时管制区检查
drone_weather           -> 天气和风速约束
drone_route_plan        -> 多无人机航线分配
drone_risk_assessment   -> 风险评估和缓解措施
drone_mission_export    -> 审批用任务计划导出
```

## 当前输出

输出包含：

- 任务类型
- 作业区域
- 无人机数量
- 巡检目标
- 航线策略
- 每架无人机的航程、预计时间、高度、速度、载荷、动作
- 风险等级
- 缓解措施
- 安全边界说明

## 安全边界

当前系统只生成 `review_only_json` 和 Markdown 说明。

不做：

- 不连接真实飞控
- 不自动起飞
- 不绕过人工审批
- 不把 LLM 输出直接当飞控命令

后续如果接真实无人机平台，应新增单独的 `mission_dispatch` tool，并强制：

- RBAC 权限
- 双人审批或持证操作员确认
- 禁飞区二次校验
- 天气二次校验
- mission 文件签名
- 完整 trace 和审计日志

## 面试亮点

这个业务展示了项目从 RAG 问答扩展到“业务 Agent 编排平台”的能力：

- Skill 是业务能力入口
- Workflow 是可配置执行图
- Tool 是确定性、安全、可审计的业务能力
- Trace 记录每一步工具调用
- 最终输出可审批计划，而不是直接执行高风险动作
