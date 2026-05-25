# RAG Evaluation Report

Generated at: 2026-05-24T12:08:33
Dataset size: 4
Elapsed: 93513.38 ms

## Ablation Summary

| Config | Retrieval | Rerank | Metadata Adj. | Recall@5 | MRR@10 | Citation Acc. | Tool Success |
|---|---|---:|---:|---:|---:|---:|---:|

## Agent Evaluation: deterministic_workflow_agent

| Metric | Value |
|---|---:|
| AgentRunSuccessRate | 100.00% |
| AgentCitationHit@5 | 0.00% |
| AnswerKeywordCoverage | 62.50% |
| AgentNodeSuccessRate | 100.00% |
| WorkflowCompletionRate | 100.00% |
| AgentToolSuccessRate | 100.00% |
| ToolSuccessRate | 100.00% |
| PlanCompleteness | 95.83% |
| ConstraintPassRate | 87.50% |
| TraceCoverage | 100.00% |
| AgentAvgLatencyMs | 23378.18 ms |

### Agent Case Details

| Case | Workflow | Plan | Constraint | Trace | Tool | Latency | Question | Nodes | Tools | Matched Keywords |
|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| mission_powerline_a | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 14127.40 ms | 明天上午 9 点让两架无人机巡检 A 区域的输电线路，重点检查杆塔和疑似异物。 | supervisor_router, mission_parse, mission_context, mission_route_plan, mission_risk_review, mission_export | drone_mission_parse, drone_map_query, drone_no_fly_zone, drone_weather, drone_route_plan, drone_risk_assessment, drone_mission_export | powerline_inspection, parallel_area_split |
| mission_night_b | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 14112.79 ms | 今晚安排一架无人机对 B 区域进行夜间边界巡检，避开敏感区域并输出审批用任务计划。 | supervisor_router, mission_parse, mission_context, mission_route_plan, mission_risk_review, mission_export | drone_mission_parse, drone_map_query, drone_no_fly_zone, drone_weather, drone_route_plan, drone_risk_assessment, drone_mission_export | night_operation |
| tool_link_budget | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 14183.61 ms | 做一个链路预算：频率 2400MHz，距离 5km，发射功率 20dBm，接收灵敏度 -90dBm。 | supervisor_router, deterministic_tool | link_budget_estimator | 链路预算估算, 2400, 5.0, risky |
| rag_quic_stream | 100.00% | 83.33% | 50.00% | 100.00% | 100.00% | 51088.94 ms | QUIC 规范中 stream 是如何工作的？ | supervisor_router, retrieval_rewritten, retrieval_original, merge_evidence, critic, retrieval_original, retrieval_rewritten, merge_evidence, critic, answer | knowledge_search, parent_context, knowledge_search, parent_context, knowledge_search, parent_context, knowledge_search, parent_context | QUIC |
