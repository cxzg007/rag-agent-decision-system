# 外部依赖可观测与重试设计

## 1. 目标

Agent 系统会调用多类外部或重型依赖：

- LLM API
- Elasticsearch / RAG 检索
- Cross-Encoder Rerank 模型
- Tool / MCP 工具
- 业务规划工具

这些依赖可能慢、超时、偶发失败或返回异常格式。为了便于定位慢调用、失败依赖和工具异常，项目新增统一外部依赖调用器 `DependencyCaller`。

## 2. 统一能力

`app/services/dependency_caller.py` 提供：

- timeout
- retry
- fallback
- structured logging
- trace_id 透传
- 慢调用标记
- 失败依赖定位
- 异常类型与异常信息记录

结构化日志事件：

```text
external_dependency_call_start
external_dependency_call_success
external_dependency_call_failed
external_dependency_fallback_used
```

日志字段包括：

```text
trace_id
name
dependency_type
attempt
max_attempts
timeout_seconds
latency_ms
slow
error_type
error_message
metadata
```

## 3. 接入位置

| 依赖类型 | 接入文件 | 说明 |
| --- | --- | --- |
| LLM | `app/services/llm.py` | OpenAI-compatible chat completion 使用 timeout/retry/fallback，并透传 Agent trace_id |
| RAG 检索 | `app/tools/knowledge_search.py` | `retriever.search` 通过统一调用器执行，失败时 fallback 为空证据 |
| Rerank | `app/services/reranker.py` | CrossEncoder / lexical rerank 通过统一调用器执行，失败时回退到原始候选 top_k |
| Tool | `app/services/agent/executor.py` | 所有 ToolSpec handler 统一执行 timeout/retry/logging |
| MCP Tool | `app/services/agent/executor.py` | MCP 调用也在 ToolExecutor 外层统一记录 |

同步模型调用会放入 `asyncio.to_thread()`，否则 `asyncio.wait_for()` 无法真正约束阻塞的模型预测。Embedding 和 Rerank 模型初始化使用显式锁保护，避免并行 Workflow 首次请求时重复加载模型。

## 4. Trace ID 透传

`ToolExecutor` 从 `AgentState.trace_id` 读取 trace，并传入 `DependencyCaller`。

`DependencyCaller` 使用 `ContextVar` 保存当前 trace，因此嵌套调用也能继承 trace：

```text
ToolExecutor(trace_id)
  -> knowledge_search
    -> retriever.search
    -> reranker.rerank
```

LLM Planner、LLM Critic、LLM Answer Generator 也显式把 `state.trace_id` 传给 `llm_client.chat_json()`。

## 5. Fallback 策略

| 场景 | fallback |
| --- | --- |
| LLM 调用失败 | 使用 deterministic planner / critic / answer 生成的 fallback JSON |
| RAG 检索失败 | 返回空候选，让上层 critic/answer 走证据不足路径 |
| Rerank 失败 | 使用原始候选 `top_k`，避免检索结果整体丢失 |
| Tool 失败 | ToolExecutor 记录失败 tool_call，Agent 可继续降级 |

## 6. 配置项

```text
LLM_TIMEOUT_SECONDS
LLM_RETRY_COUNT
RAG_RETRIEVAL_TIMEOUT_SECONDS
RAG_RETRIEVAL_RETRY_COUNT
RERANK_TIMEOUT_SECONDS
RERANK_RETRY_COUNT
SLOW_DEPENDENCY_THRESHOLD_MS
```

## 7. 面试表达

可以这样讲：

> 我把 LLM、RAG 检索、Rerank 和工具执行统一封装成 DependencyCaller，所有外部依赖调用都具备 timeout、retry、fallback、structured logging 和 trace_id 透传。这样线上如果出现慢调用、ES 瞬时失败、Rerank 模型卡顿或工具异常，可以通过同一个 trace_id 串起完整链路，并且系统不会因为单个依赖失败直接崩掉。
