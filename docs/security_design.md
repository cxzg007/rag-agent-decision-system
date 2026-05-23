# 权限与安全设计

## 1. 目标

当前安全层聚焦 Agent 项目最核心的风险：

- 未授权访问调试和写入接口
- Workflow / LLM Planner 调用越权工具
- 用户输入过长或格式异常
- 工具调用失败后不可观测
- Workflow condition 执行任意代码

## 2. API Key 鉴权

配置：

```text
REQUIRE_API_KEY=false
API_KEY=
```

开启后，请求受保护接口必须带：

```text
X-API-Key: <API_KEY>
```

已保护接口：

```text
POST /documents/upload
POST /eval/run
POST /memory
GET  /traces
GET  /traces/{trace_id}
GET  /workflows/{workflow_run_id}
```

`/workflows/run` 暂时保持公开，方便作为主要业务入口；`/health` 保持公开，方便健康检查。

## 3. 输入校验

Workflow request 限制：

```text
question: 非空，最大 MAX_QUESTION_LENGTH
session_id: 只允许 a-zA-Z0-9_.:-
workflow_id: 只允许 a-zA-Z0-9_.:-
top_k: 1 到 20
```

Memory request 限制：

```text
session_id: 安全字符
memory_type: 安全字符
content: 非空，最大 MAX_QUESTION_LENGTH
importance: 0 到 1
```

## 4. 工具权限

每个工具都有 scope：

```text
knowledge_search -> retrieval
parent_context   -> retrieval
memory_read      -> memory
plan_generator   -> planning
web_search       -> external
```

配置：

```text
ALLOWED_TOOL_SCOPES=retrieval,memory,planning
```

默认不允许 `external`，因此预留的 `web_search` 不会被误调用。

如果工具 scope 不允许，ToolExecutor 会记录失败：

```text
success=false
output_summary=tool scope not allowed: retrieval
```

Workflow 会返回降级答案，而不是直接崩溃。

## 5. Workflow Condition 安全

Workflow condition 没有使用 Python `eval`。

只支持白名单 DSL：

```text
==
in
and
or
true / false
string literal
list literal
```

变量也只允许从受控字段和 `WorkflowState.variables` 读取。

## 6. 当前限制

当前安全层仍是 MVP：

- API Key 是单 key，不支持多用户/多租户
- 没有 RBAC
- 没有速率限制
- 没有请求体大小中间件
- 没有审计日志表
- 没有 PII 脱敏
- 没有 prompt injection 专门检测

下一步建议：

- 增加 `security_events` 表
- 对 `/workflows/run` 增加可选鉴权策略
- 增加 rate limit
- 增加 LLM prompt injection 检测节点
- 增加 memory 写入前的隐私过滤
