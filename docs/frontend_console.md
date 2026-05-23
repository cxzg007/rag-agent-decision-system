# 前端控制台说明

## 1. 入口

```text
GET /
GET /app/
```

根路径会跳转到 `/app/`。

## 2. 页面模块

当前前端是 FastAPI 托管的轻量静态控制台，不需要 Node/React 构建链。

```text
Overview  -> 健康状态和依赖状态
Skills    -> 执行 /skills/{skill_id}/run 和 /stream
Workflow  -> 执行 /workflows/run 和 /stream
Traces    -> 查询 trace 列表和详情
Eval      -> 查看 /eval/dataset，并触发 /eval/run
Registry  -> 查看 Skill / MCP / Workflow registry
```

## 3. 鉴权

页面顶部可保存 API Key 到浏览器 localStorage。请求会自动带：

```text
X-API-Key
```

这是本地演示和内部控制台方案。生产环境应升级为用户登录、短期 token、RBAC 和操作审计。

## 4. 评测集可视化

Eval 面板支持：

- 选择 `default` 或 `large` 评测集。
- 查看样本数、字段数、消融维度数。
- 按来源文档展示数据分布。
- 展示 gold chunk 数量分布。
- 展示 answer keyword 数量分布。
- 查看样本问题、来源文档、gold chunks 和关键词。
- 选择是否包含 Agent Eval 后触发 `/eval/run`。
- 将 Recall@5、MRR@10、CitationAccuracy、ToolSuccessRate 等消融指标渲染成柱状对比图。
- 将 AgentRunSuccessRate、AgentCitationHit@5、AnswerKeywordCoverage、AgentAvgLatencyMs 等 Agent 指标渲染成图表。

对应接口：

```text
GET /eval/dataset?name=default&sample_size=12
GET /eval/dataset?name=large&sample_size=12
POST /eval/run
```

## 5. 设计取舍

当前选择静态控制台而不是 React SPA，原因：

- 项目重点是 Agent/RAG 后端工程能力，前端用于产品化演示和运维排查。
- 不引入额外构建链，容器镜像和本地启动更简单。
- 所有功能通过现有 API 编排，不额外复制业务逻辑。
- UI 文案以中文为主，保留 API Key、Trace、Recall、MRR 等面试和工程语境中常用英文术语。

## 6. 验证

```powershell
python scripts/smoke_api.py --strict-ready
```

smoke 会检查：

```text
/app/
/app/app.js
/eval/dataset
/health/live
/health/ready
/skills
/mcp/servers
/workflows
```
