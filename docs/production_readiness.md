# 生产化补强说明

## 1. 运行方式

本地开发：

```powershell
docker compose up -d
python scripts/upgrade_db.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

容器化 API：

```powershell
docker compose --profile api up -d --build
```

前端控制台：

```text
http://localhost:8000/app/
```

## 2. 健康检查

```text
GET /health/live
GET /health/ready
GET /health
```

- `/health/live`: 只证明 API 进程存活，适合容器 liveness probe。
- `/health/ready`: 检查 Elasticsearch、Redis、PostgreSQL；依赖不可用时返回 503，适合 readiness probe。
- `/health`: 返回完整依赖状态，用于人工排障。

## 3. 配置

关键生产配置：

```text
APP_ENV=production
LOG_LEVEL=INFO
REQUIRE_API_KEY=true
API_KEY=<strong-secret>
ALLOWED_TOOL_SCOPES=retrieval,memory,planning
```

外部 MCP 工具需要显式开启：

```text
ALLOWED_TOOL_SCOPES=retrieval,memory,planning,external
```

## 4. 部署前检查

配置和依赖检查：

```powershell
python scripts/preflight.py
python scripts/preflight.py --strict-deps
```

API 冒烟测试：

```powershell
python scripts/smoke_api.py
python scripts/smoke_api.py --strict-ready
```

## 6. Skill 产品入口

Skill 不只是 catalog，也可以作为产品 API 入口：

```text
POST /skills/{skill_id}/run
POST /skills/{skill_id}/stream
```

执行入口会：

```text
读取 config/skills/{skill}.json
校验 skill.enabled
合并 default_inputs 和 request.inputs
只允许覆盖 workflow-safe 字段
调用绑定 workflow_id
返回 workflow response 或 SSE events
```

这两个接口会触发 workflow、工具调用、记忆写入和 trace 落库，因此需要 API Key。

## 7. 日志

已启用请求日志中间件，每个响应都会带：

```text
X-Request-ID
X-Process-Time-Ms
```

日志记录：

```text
request_id
method
path
status
latency_ms
```

## 8. 仍需补强

- 正式 Alembic migration。
- 结构化 JSON 日志。
- Prometheus 指标。
- 异步任务队列处理大文件 ingestion。
- 更严格的外部 MCP server allowlist。
