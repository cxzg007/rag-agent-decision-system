# Agent 评测设计

## 1. 目标

RAG 检索评测只能说明证据是否召回，不能完整说明无人机任务规划链路是否可靠。因此项目新增 Agent 层评测，用于同时衡量检索质量与任务规划链路可靠性。

Agent 评测数据集：

```text
app/eval/agent_dataset.jsonl
```

当前覆盖：

- 无人机输电线路巡检任务
- 夜间边界巡检任务
- 链路预算确定性工具任务
- RAG 规范查询任务

## 2. 指标定义

| 指标 | 含义 |
| --- | --- |
| `ToolSuccessRate` | 工具调用成功率，统计 Tool/MCP 调用是否成功返回 |
| `WorkflowCompletionRate` | 工作流完成率，判断预期节点是否成功执行并到达终止节点 |
| `PlanCompleteness` | 任务计划完整性，综合预期节点覆盖、预期工具覆盖和结构化输出/约束通过情况 |
| `ConstraintPassRate` | 约束校验通过率，检查审批、review-only 导出、风险等级、航线、缓解措施、禁止 dispatch 等约束 |
| `TraceCoverage` | Trace 覆盖率，检查 trace_id、workflow_run_id、node latency、tool latency 和预期工具记录是否齐全 |

保留的通用 Agent 指标：

- `AgentRunSuccessRate`
- `AgentCitationHit@5`
- `AnswerKeywordCoverage`
- `AgentNodeSuccessRate`
- `AgentAvgLatencyMs`

## 3. 为什么单独建 Agent 数据集

无人机任务规划样本没有 `gold_chunk_ids`，如果直接塞进 RAG 检索评测集，会污染 Recall@K、MRR 等检索指标。

因此项目把评测拆成两层：

```text
RAG eval dataset      -> 衡量检索质量
Agent eval dataset    -> 衡量任务规划链路可靠性
```

这样既能做检索消融，也能评估真实业务 workflow。

## 4. 运行方式

运行完整报告：

```powershell
python scripts/run_eval_report.py --output reports/eval_report.md
```

仅运行 Agent 评测：

```powershell
python scripts/run_eval_report.py --agent-only --output reports/agent_eval_report.md
```

指定 Agent 数据集：

```powershell
python scripts/run_eval_report.py --agent-only --agent-dataset app/eval/agent_dataset.jsonl --output reports/agent_eval_report.md
```

## 5. 当前验证结果

在 Docker Desktop 未启动、ES/Redis/PostgreSQL 不可用的本地环境下，Agent-only 报告仍可生成。无人机任务规划和链路预算样例的链路指标验证通过；RAG 样例因 ES 不可用走 fallback，导致引用相关指标降低。

当前 `reports/agent_eval_report.md` 中核心 Agent 指标：

```text
AgentRunSuccessRate      100.00%
WorkflowCompletionRate   100.00%
ToolSuccessRate          100.00%
PlanCompleteness          95.83%
ConstraintPassRate        87.50%
TraceCoverage            100.00%
```

说明：`ConstraintPassRate` 低于 100% 的主要原因是 RAG 样例在当前本地依赖不可用时无法取得 citation；启动 Docker 后重新运行会得到更完整的检索侧结果。
