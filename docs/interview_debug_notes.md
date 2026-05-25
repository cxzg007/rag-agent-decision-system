# 面试排障记录

这份文档记录 RAG Agent 项目实现过程中比较重要、适合在面试中讲出来的问题。重点不是简单罗列报错，而是体现工程判断：依赖兼容、服务降级、检索质量、元数据质量和本地部署可复现性。

后续开发约定：每完成一个重要功能，都同步记录实现过程中遇到的关键问题、处理方式和面试可讲点，避免只留下代码而丢失工程决策过程。

## 2026-05-24：补全 Agent 层评测指标

### 背景

之前评测更偏 RAG 检索链路，已经包含 Recall@5、MRR@10、CitationAccuracy 等指标。但无人机任务规划系统不能只看检索是否命中，还要看 Agent workflow 是否完整执行、工具是否成功、约束是否通过、trace 是否足够回放。

### 处理

新增独立 Agent 评测数据集：

```text
app/eval/agent_dataset.jsonl
```

新增/补全 Agent 层指标：

```text
ToolSuccessRate
WorkflowCompletionRate
PlanCompleteness
ConstraintPassRate
TraceCoverage
```

同时更新：

```text
app/eval/metrics.py
app/schemas/eval.py
scripts/run_eval_report.py
app/api/eval.py
app/static/app.js
docs/agent_evaluation.md
reports/agent_eval_report.md
tests/test_agent_eval_metrics.py
```

报告脚本新增：

```powershell
python scripts/run_eval_report.py --agent-only --output reports/agent_eval_report.md
```

### 重要问题 1：无人机任务规划样本不适合混入 RAG 检索评测集

现象：

无人机任务规划样本没有 `gold_chunk_ids`，如果直接放入 `app/eval/dataset.jsonl`，会破坏 Recall@K、MRR、CitationAccuracy 等检索指标。

解决：

单独建立 `app/eval/agent_dataset.jsonl`，Agent 样本使用：

```text
expected_nodes
expected_tools
answer_keywords
constraints
workflow_id
```

面试可讲点：

RAG 评测和 Agent 评测不是同一层问题。检索评测关注证据召回；Agent 评测关注任务链路是否可靠，应该拆开建数据集和指标。

### 重要问题 2：PlanCompleteness 不应被答案关键词强绑定

现象：

最初 `PlanCompleteness` 参考了 `answer_keywords` 覆盖率，导致无人机任务的结构化计划已经完整生成，但因为 Markdown 中未显式出现某些关键词，计划完整性被低估。

解决：

将 `PlanCompleteness` 改为：

```text
expected node coverage
expected tool coverage
constraint pass rate
```

这样更符合无人机任务规划场景：任务是否完整，主要看规划节点、业务工具和安全约束是否闭环，而不是自然语言答案中是否出现某个词。

面试可讲点：

指标设计要贴合业务语义。Agent 评测不能照搬 RAG 的关键词覆盖率，否则会误判结构化任务规划能力。

### 重要问题 3：当前本地依赖不可用会拉低 RAG 样例的 Agent 指标

现象：

当前 Docker Desktop 未启动，ES/Redis/PostgreSQL 不可用。运行 Agent-only 报告时，无人机和链路预算样例可完成；RAG 样例走 retrieval fallback，导致 citation 相关约束未完全通过。

当前报告：

```text
AgentRunSuccessRate      100.00%
WorkflowCompletionRate   100.00%
ToolSuccessRate          100.00%
PlanCompleteness          95.83%
ConstraintPassRate        87.50%
TraceCoverage            100.00%
```

新增轻量单元测试 `tests/test_agent_eval_metrics.py`，不用启动 ES/Redis/PostgreSQL，也能验证五个 Agent 指标在完整任务计划场景下计算为 100%。

解决：

保留真实依赖状态，不为了刷指标隐藏 ES 不可用问题。报告和文档中明确说明：启动 Docker 后重新运行可得到完整 RAG 样例结果。

面试可讲点：

Agent 评测结果会受任务类型和外部依赖状态影响，因此报告里要解释数据来源和运行环境。这样比只给一个漂亮数字更可信。

## 2026-05-23：统一外部依赖调用器

### 背景

项目已经接入 LLM、Elasticsearch、Rerank 模型、Tool Registry 和 MCP Tool。早期这些调用点各自处理 timeout、retry 或异常，有几个问题：

- LLM、RAG、Rerank、Tool 的日志字段不一致
- trace_id 不能稳定贯穿嵌套调用
- 慢调用不容易定位
- 失败依赖和工具异常需要到不同模块里排查
- fallback 策略分散，面试时不容易讲清楚工程边界

### 处理

新增统一外部依赖调用器：

```text
app/services/dependency_caller.py
```

统一提供：

```text
timeout
retry
fallback
structured logging
trace_id 透传
slow call 标记
error_type / error_message 记录
```

接入位置：

```text
LLM: app/services/llm.py
RAG retrieval: app/tools/knowledge_search.py
Rerank: app/services/reranker.py
Tool/MCP: app/services/agent/executor.py
```

新增文档：

```text
docs/external_dependency_observability.md
```

新增测试：

```text
tests/conftest.py
tests/test_dependency_caller.py
```

### 重要问题 1：pytest 找不到 `app` 包

现象：

```text
ModuleNotFoundError: No module named 'app'
```

原因：

项目之前主要通过脚本直接运行，脚本里会手动把项目根目录加入 `sys.path`。新增 `tests/` 后，pytest 从测试目录收集文件时没有自动把项目根目录加入模块搜索路径。

解决：

新增 `tests/conftest.py`：

```python
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

面试可讲点：

工程化项目不能只依赖“从某个目录手动运行脚本”的隐式路径。测试环境要显式固定 import root，否则 CI、本机和 IDE 的行为可能不一致。

### 重要问题 2：同步 Rerank 模型不能只用 `asyncio.wait_for`

现象：

CrossEncoder 的 `predict()` 是同步阻塞调用。如果直接把同步函数包进 `asyncio.wait_for`，函数会先阻塞事件循环，timeout 不能真正中断模型预测。

解决：

Rerank 接入 `DependencyCaller` 时，使用：

```python
asyncio.to_thread(self._cross_encoder_rerank, ...)
```

这样同步模型预测在线程中执行，外层 timeout 才有实际意义。失败时 fallback 到原始候选 `top_k`，避免检索结果全部丢失。

面试可讲点：

不是所有 timeout 都真的有效。对同步阻塞依赖，需要放入线程池、进程池或独立服务，否则事件循环层面的 timeout 只能等阻塞结束后才生效。

### 重要问题 3：并行 RAG 分支可能重复冷启动模型

现象：

验证 Supervisor 的 RAG 路径时，`retrieval_original` 和 `retrieval_rewritten` 并行执行。日志显示两个分支都可能同时触发 embedding / CrossEncoder 模型冷启动，导致 HuggingFace metadata 检查和模型加载日志重复出现。

原因：

Python 3.12 中 `functools.cached_property` 不再提供内部锁。并行分支首次访问模型属性时，可能同时进入加载逻辑，造成重复初始化。

解决：

将 `EmbeddingService.model` 和 `Reranker.model` 从 `cached_property` 改为显式锁保护：

```text
threading.Lock
_model
_model_loaded
```

同时把 embedding 查询和 CrossEncoder rerank 放入 `asyncio.to_thread()`，减少同步模型计算阻塞事件循环的问题。

面试可讲点：

并行 Workflow 不只是“更快”，也会放大冷启动和共享资源竞争问题。模型、连接池、缓存这类共享资源需要考虑并发初始化保护。

### 重要处理 4：不同依赖使用不同 fallback

本次没有用“一刀切返回 None”的 fallback，而是按依赖语义处理：

```text
LLM 失败       -> deterministic fallback JSON
RAG 检索失败   -> 空候选，让上层进入证据不足路径
Rerank 失败    -> 原始候选 top_k
Tool 失败      -> tool_call 记录失败，由 Agent 降级
```

面试可讲点：

fallback 不是隐藏错误，而是把错误控制在可解释边界内。不同依赖的 fallback 应该服务于业务语义，而不是统一吞异常。

### 当前验证结论

```powershell
python -m compileall app scripts tests
pytest tests\test_dependency_caller.py -q
python scripts\preflight.py
python scripts\smoke_api.py --strict-ready
```

结果：

```text
compileall passed
2 dependency caller tests passed
preflight passed，但 health=degraded
smoke functional endpoints passed，strict-ready 因外部依赖不可用返回 503
non-strict smoke passed
RAG supervisor path returned 200
```

RAG 路径验证中，统一调用器成功打出：

```text
dependency_type=tool name=knowledge_search
dependency_type=rag_retrieval name=retriever.search
dependency_type=rerank name=reranker.cross_encoder
trace_id=同一个 Agent trace
slow=true 标记模型冷启动和检索慢调用
```

### 重要问题 5：Docker Desktop 未启动导致 strict-ready 失败

现象：

2026-05-24 推送前重新验证时：

```text
docker compose ps
open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.

python scripts\preflight.py
health=degraded
elasticsearch: down Connection timed out
redis: down
postgresql: down connection timeout expired

python scripts\smoke_api.py --strict-ready
GET /health/ready -> 503
```

同时，非外部依赖强相关的功能路径仍返回 200：

```text
GET /health/live -> 200
GET /app/ -> 200
GET /skills -> 200
GET /workflows -> 200
POST /skills/agent_supervisor/run direct -> 200
POST /skills/agent_supervisor/run tool -> 200
POST /skills/drone_mission_planner/run -> 200
```

原因：

Docker Desktop 没有运行，本机没有 `dockerDesktopLinuxEngine` pipe，因此 Docker Compose 管理的 Elasticsearch、Redis、PostgreSQL 都不可达。`--strict-ready` 会要求所有外部依赖可用，所以返回 503 是符合预期的。

处理：

本次没有为了通过 strict-ready 修改健康检查语义，而是保留真实依赖状态：

- 代码编译通过
- `DependencyCaller` 单测通过
- preflight 能明确报告 degraded 依赖
- smoke 中核心 API 和不依赖 ES/Redis/PostgreSQL 的 Agent 路径通过

面试可讲点：

健康检查要真实反映依赖状态，不能为了测试通过把外部依赖失败隐藏掉。生产环境可以区分 liveness 和 readiness：进程活着不等于依赖可服务。

## 2026-05-23：将 Multi-Agent 修正为 Supervisor 路由驱动 Workflow

### 背景

原先的表达容易让人理解成“所有任务都会走完整 Multi-Agent 流程”。这在工程上并不合理：简单概念解释、规范查询、链路预算和复杂无人机任务规划的复杂度不同，不应该共享同一条重型链路。

### 处理

本次把系统修正为 Router-driven Workflow Graph：

```text
agent_supervisor
  -> supervisor_router
  -> direct_answer / RAG Skill / deterministic_tool / mission_planning
```

关键改动：

- 新增 `config/workflows/supervisor_workflow_v1.json`
- 新增 `config/skills/agent_supervisor.json`
- 将 `drone_mission_planner` Skill 接入 `supervisor_workflow_v1`
- 新增 `link_budget_estimator` 确定性工具，用于链路预算和覆盖估计类任务
- `WorkflowRuntime` 支持 `direct_answer`、`deterministic_tool`、`mission_export` 作为终止节点
- `smoke_api.py` 增加 Direct Answer、Deterministic Tool、Mission Planning 三条路径验证

### 重要问题 1：冒烟测试仍断言旧 workflow_id

现象：

```text
drone smoke used unexpected workflow_id
```

原因：

无人机 Skill 已经改为接入 `supervisor_workflow_v1`，但 `scripts/smoke_api.py` 仍然断言旧的 `drone_mission_planning_v1`。这属于测试契约没有跟随架构演进更新。

解决：

更新 smoke 测试，断言：

```text
workflow_id == supervisor_workflow_v1
node_runs[0] == supervisor_router
node_runs[-1] == mission_export
```

同时增加 `agent_supervisor` 的 direct/tool 路径测试，避免只测无人机分支。

面试可讲点：

架构升级不能只改代码，还要同步更新契约测试。否则测试会把正确的新行为误报成失败。

### 重要问题 2：PowerShell 中文 here-string 导致路由误判

现象：

本地用 PowerShell here-string 直接写中文问题做临时测试时，请求内容变成了 `????`，导致 Supervisor 无法识别“无人机”“链路预算”等关键词，最终全部落到默认 RAG 分支。

原因：

这不是路由逻辑错误，而是终端编码和脚本输入方式导致中文在传入 Python 前已经丢失。

解决：

临时测试脚本统一使用 Unicode escape 构造中文字符串，例如：

```python
"\u65e0\u4eba\u673a"
```

正式 smoke 测试也使用 Unicode escape，保证在 Windows PowerShell 和 CI 环境中都稳定。

面试可讲点：

中文项目的测试要注意编码稳定性。遇到“模型或路由不识别中文”时，先确认输入在进程内是否仍然是正确 Unicode，而不是直接怀疑业务逻辑。

### 重要问题 3：RAG 分支出现 ES 瞬时异常但整体恢复

现象：

临时验证 RAG 路径时，Elasticsearch 查询曾出现一次 `status:N/A` 的瞬时异常，节点重试后请求成功返回。

原因：

本地 ES 和 embedding/rerank 模型存在冷启动、连接复用和服务准备时间问题。短时间内触发并发检索时，偶发连接层异常是可预期的。

解决：

当前 Workflow 节点保留 timeout、retry 和节点级失败记录。RAG 分支在重试后成功，trace 中可以看到节点状态和耗时。

面试可讲点：

Agent 系统依赖外部服务，不能假设每个工具调用都稳定。节点级 retry、timeout、trace 和降级策略是生产化 Agent 的关键能力。

### 当前验证结论

使用 Unicode 稳定输入后，四类路径均已验证：

```text
简单解释     -> supervisor_router -> direct_answer
链路预算     -> supervisor_router -> deterministic_tool -> link_budget_estimator
规范查询     -> supervisor_router -> retrieval_original/retrieval_rewritten -> merge -> critic -> answer
无人机规划   -> supervisor_router -> mission_parse -> mission_context -> mission_route_plan -> mission_risk_review -> mission_export
```

本次最终验证命令：

```powershell
python -m compileall app scripts
python scripts/preflight.py
python scripts/smoke_api.py --strict-ready
```

验证结果：

```text
compileall passed
preflight passed: skills=4 mcp_servers=2 workflows=3 health=ok
smoke passed: direct/tool/mission paths all returned 200
RAG supervisor path returned 200 and executed knowledge_search + parent_context
```

### 重要问题 4：模型冷启动会拉长首次 RAG 验证耗时

现象：

RAG 路由验证第一次运行时出现较多 HuggingFace `HEAD/GET` 日志和未鉴权 warning，整体请求耗时约 22 秒。

原因：

本地首次加载 embedding 模型和 rerank 模型时，会检查 HuggingFace Hub 元数据并加载权重。模型缓存后后续请求会明显更快。这个现象不是路由错误，而是模型冷启动成本。

解决：

当前 smoke 测试默认不把完整 RAG 路径作为强制项，避免每次快速健康检查都被模型冷启动拖慢；完整 RAG 路径通过单独验证脚本确认。

面试可讲点：

RAG 系统的“功能正确”和“启动性能”要分开验证。生产环境可以通过模型预热、本地模型缓存、镜像内置权重或独立 embedding/rerank 服务降低冷启动影响。

### 重要处理 5：确定性工具要解析业务参数，而不是只依赖默认值

现象：

链路预算工具最初能解析频率、距离和发射功率，但接收灵敏度主要依赖默认值。测试样例里默认值刚好等于用户输入的 `-90dBm`，因此结果看起来正确，但工程上不够严谨。

处理：

为 `link_budget_estimator` 增加 label-aware 参数解析：

```text
发射功率 20dBm
接收灵敏度 -90dBm
```

解析时优先匹配带业务标签的数值，再回退到通用单位匹配。

面试可讲点：

确定性工具的价值在于可解释和可复现，所以不能只靠默认参数“碰巧正确”。面试中可以强调：Tool 层需要明确输入 schema、参数解析、默认值、假设说明和输出审计字段。

### 重要问题 6：通用单位回退会把发射功率误当成接收灵敏度

现象：

为链路预算工具增加接收灵敏度解析后，临时验证发现一个边界问题：

```text
发射功率 20dBm，接收灵敏度 -85dBm
```

如果中文 label 因编码或格式原因没有命中，接收灵敏度解析会回退到“第一个 dBm 数值”，错误地取到 `20dBm`，导致链路余量计算严重失真。

解决：

将 `_extract_labeled_number` 增加 `fallback_to_unit` 参数：

- 发射功率允许回退到第一个 `dBm`
- 接收灵敏度不允许通用回退，label 未命中时使用 schema 默认值

并用 Unicode escape 构造中文验证样例，确认：

```text
receiver_sensitivity=-85.0 dBm
link_margin_db=-8.02
```

面试可讲点：

工具参数解析不能只看“有没有数值”，还要看数值语义是否匹配。对于同单位的多个参数，label-aware parsing 和安全默认值比盲目正则更可靠。

### 重要问题 7：GitHub HTTPS 推送被连接重置

现象：

提交后执行：

```powershell
git push origin main
```

出现：

```text
fatal: unable to access 'https://github.com/cxzg007/rag-agent-decision-system.git/': Recv failure: Connection was reset
```

原因：

这是网络传输层错误，说明 HTTPS 连接在接收过程中被重置。它通常和本地网络、代理、TLS 连接或 GitHub 短暂连接状态有关，不代表提交内容或仓库权限一定有问题。

解决：

先确认本地 commit 已经创建成功，再记录错误，然后重试 `git push origin main`。如果持续失败，再检查：

- `gh auth status`
- GitHub token 权限
- 网络代理或 VPN
- 是否需要改用 SSH remote

面试可讲点：

发布链路也需要可诊断性。遇到 push 失败时，要先区分“代码/权限问题”和“网络传输问题”，避免误回滚已经验证通过的代码。

## 0. 为什么本地经常出现 Docker / PostgreSQL 不可用

### 现象

开发过程中多次看到类似问题：

```text
Docker Desktop pipe not found
PostgreSQL 127.0.0.1:15432 不可达
Elasticsearch localhost:9200 不可达
Redis localhost:6379 连接失败
```

### 原因

这个项目的基础设施不是内嵌在 FastAPI 进程里的，而是通过 Docker Compose 启动：

```text
Elasticsearch
Redis
PostgreSQL
```

只要 Docker Desktop 停止，这些容器就不可访问，本机映射端口也会断开。因此这类错误通常不是业务代码坏了，而是本地依赖服务没有运行。

### 解决方案

需要真实检索、memory 或 trace 写库时，先启动 Docker：

```powershell
docker compose up -d
```

然后做数据库迁移：

```powershell
python scripts/upgrade_db.py
```

代码层面也做了降级：

```text
Redis 不可用：memory 返回空 / 写入跳过
PostgreSQL 不可用：trace/feedback 查询返回 503
Elasticsearch 不可用：工具调用失败被记录，Agent 返回可控降级答案
```

### 面试可讲点

AI 应用通常依赖多个外部服务。开发环境下依赖不可用很常见，所以要做健康检查、快速失败、清晰错误和非核心能力降级，而不是让主链路无提示卡死。

## 1. Elasticsearch 客户端和服务端版本不匹配

### 现象

检查 ES 索引是否存在时，Python 客户端报错：

```text
elasticsearch.BadRequestError: BadRequestError(400, 'None')
```

### 原因

一开始 Python 客户端使用的是：

```text
elasticsearch==9.2.0
```

但 Docker 中运行的 Elasticsearch 是：

```text
Elasticsearch 8.15.3
```

客户端和服务端主版本不一致，导致部分 API 行为不兼容。

### 解决方案

将 Python 客户端版本降到 ES 8.x 同主版本：

```text
elasticsearch[async]==8.15.1
```

重新安装：

```powershell
python -m pip install "elasticsearch[async]==8.15.1"
```

### 面试可讲点

搜索基础设施对版本兼容比较敏感。实际项目中应该明确记录 ES 服务端版本和客户端版本，并在依赖文件中固定版本，避免部署环境变化导致检索链路不可用。

## 2. Redis 不可用导致 `/chat` 接口返回 500

### 现象

Redis 没有运行时，`/chat` 接口报错：

```text
redis.exceptions.ConnectionError: Error 22 connecting to localhost:6379
```

### 原因

Agent 在生成答案后会把用户问题和助手回答写入 Redis，作为 session 级短期记忆。一开始 Redis 被当成强依赖，只要写 memory 失败，整个请求就会失败。

### 解决方案

将 Redis memory 改成可降级能力。

写入失败时跳过：

```python
try:
    await self.client.rpush(...)
except Exception:
    return
```

读取失败时返回空列表：

```python
except Exception:
    return []
```

### 面试可讲点

Redis 在这个系统中用于短期记忆和缓存，但它不应该阻塞主问答链路。RAG 问答的核心依赖是检索和生成，memory 是增强能力，所以应该允许降级。

## 3. Elasticsearch 不可用时工具调用失败

### 现象

Docker Desktop 停止后，ES 无法连接：

```text
Cannot connect to host localhost:9200
```

### 原因

`knowledge_search` 工具依赖 Elasticsearch。如果 ES 停止，知识库检索无法执行。

### 解决方案

在 Agent 的工具执行器中捕获异常，不让工具错误直接导致 API 崩溃。

工具失败时记录：

```text
success = false
output_summary = 错误信息
```

Agent 最终返回可控的降级答案：

```text
I could not find enough evidence in the indexed knowledge base...
```

### 面试可讲点

Agent 系统中工具调用是外部依赖，必须具备失败隔离能力。工具失败应该进入 trace 或 tool_calls，方便排查，而不是让整个 Agent 请求直接崩溃。

## 4. Chunk 元数据质量影响检索结果

### 现象

部分 RFC 文档的 chunk 出现了错误 section：

```text
section=5 December 2017, <https://www.ietf.org/
```

### 原因

章节识别正则太宽，把参考文献中的日期、编号等内容误识别成章节标题。

### 解决方案

收紧 RFC 章节识别规则，只匹配类似 `8. Title`、`15.5. Title` 这样的正式章节：

```python
SECTION_RE = re.compile(
    r"^(?P<number>\d+(?:\.\d+)*\.)\s+(?P<title>[A-Z0-9][^\n]{2,160})$"
)
```

同时过滤一些明显不像章节标题的行：

```python
if stripped.endswith(".") or "..." in stripped:
    continue
```

### 面试可讲点

RAG 效果不只是模型问题。文档解析、结构识别、元数据抽取会直接影响召回、引用、父子 chunk 扩展和最终答案可信度。高质量 metadata 是技术文档 RAG 的关键。

## 5. CrossEncoder Rerank 把 References 片段排得过高

### 现象

用户问 TLS 反重放机制时，rerank 有时会把 References 章节附近的 chunk 排到前面。

### 原因

CrossEncoder 只判断 query 和文本的相关性。如果 References 章节中包含了相关关键词，它也可能给出较高分数。但对于协议机制类问题，正文中的协议描述通常比参考文献更适合作为证据。

### 解决方案

在 rerank 阶段加入轻量的元数据规则。

如果 section 是 References，且用户不是在问参考文献，则降低分数：

```python
if "reference" in section and "reference" not in query_terms:
    adjustment -= 3.0
```

如果 section 标题和问题关键词有重合，则给一点加权：

```python
adjustment += min(len(overlap) * 0.35, 1.4)
```

### 面试可讲点

Rerank 不一定只能依赖模型分数。技术文档场景下，章节类型、文档结构、来源可信度等 metadata 可以作为排序特征，帮助提升最终证据质量。

## 6. PostgreSQL 本地端口冲突

### 现象

Docker 启动 PostgreSQL 时端口绑定失败：

```text
ports are not available: exposing port TCP 0.0.0.0:5432
```

尝试 `5433` 也失败。

### 原因

本机可能已有 PostgreSQL 服务，或者 Windows 保留了相关端口。

### 解决方案

将 PostgreSQL 宿主机端口改为更高位的端口：

```yaml
ports:
  - "15432:5432"
```

同步修改数据库连接配置：

```text
DATABASE_URL=postgresql+psycopg://agent:agent@localhost:15432/agent
```

### 面试可讲点

本地部署要考虑开发者机器上的端口冲突。Docker Compose 不应该强依赖默认端口，尤其是 PostgreSQL、MySQL、Redis 这类常见服务。

## 7. 直接运行脚本时找不到 `app` 包

### 现象

运行脚本时报错：

```text
ModuleNotFoundError: No module named 'app'
```

相关脚本包括：

```text
scripts/chunk_dataset.py
scripts/index_chunks.py
scripts/search_chunks.py
scripts/init_db.py
```

### 原因

执行：

```powershell
python scripts/index_chunks.py
```

时，Python 默认把 `scripts/` 目录加入 `sys.path`，而不是项目根目录，所以找不到 `app` 包。

### 解决方案

在可直接运行的脚本中加入项目根目录：

```python
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

### 面试可讲点

工程脚本的可用性很重要。入库、切块、检索、初始化数据库这些脚本应该能被直接运行，降低复现成本，也方便面试演示。

## 8. PowerShell 下 JSON 和 Shell 语法问题

### 现象

用 `curl.exe` 测试 SSE 接口时，因为 JSON 转义错误导致：

```text
JSON decode error
curl: (6) Could not resolve host
curl: (3) unmatched close brace/bracket
```

另外，误用了 Bash 的 here-doc 语法：

```bash
python - <<'PY'
```

在 PowerShell 中会报：

```text
The '<' operator is reserved for future use.
```

### 原因

PowerShell 和 Bash 的字符串转义、重定向语法不同。直接复制 Bash 写法在 Windows PowerShell 中容易失败。

### 解决方案

使用 PowerShell 原生方式生成 JSON：

```powershell
$body = @{
  question = 'How does TLS 1.3 prevent replay attacks?'
  session_id = 'agent-demo'
  top_k = 2
} | ConvertTo-Json -Compress

Invoke-WebRequest -Method Post `
  -Uri 'http://127.0.0.1:8000/chat/stream' `
  -ContentType 'application/json' `
  -Body $body
```

运行多行 Python 时使用 PowerShell here-string：

```powershell
@'
print("hello")
'@ | python -
```

### 面试可讲点

项目文档和调试命令要贴合目标环境。这个项目是在 Windows PowerShell 下开发的，所以 README 和调试命令需要避免 Bash 专属语法，保证可复现。

## 9. SQLAlchemy `create_all` 不会自动更新旧表结构

### 现象

为了持久化 Agent trace，我给 `chat_tasks` 增加了字段：

```text
task_type
citations
reflections
```

但如果数据库里已经存在旧版 `chat_tasks` 表，仅执行：

```python
Base.metadata.create_all(bind=engine)
```

不会自动给旧表增加新列。

### 原因

`create_all` 只负责创建不存在的表，不负责 schema migration。已有表结构变化需要显式迁移。

### 解决方案

新增轻量迁移脚本：

```text
scripts/upgrade_db.py
```

逻辑是：

```python
Base.metadata.create_all(bind=engine)
```

然后检查字段是否存在，不存在就执行：

```sql
ALTER TABLE chat_tasks ADD COLUMN ...
```

### 面试可讲点

开发阶段可以用轻量脚本快速演进表结构，但正式项目应该使用 Alembic 这类 migration 工具管理数据库 schema，保证多环境升级可控。

## 10. Trace 持久化不能影响主问答链路

### 现象

Agent 已经完成检索和答案生成后，如果 PostgreSQL 临时不可用，理论上可能因为保存 trace 失败导致接口返回 500。

### 原因

Trace 属于可观测性数据，不是生成答案的核心依赖。如果把它作为强依赖，会降低主链路可用性。

### 解决方案

在 `trace_store` 中捕获数据库异常：

```python
try:
    session.commit()
except SQLAlchemyError as exc:
    logger.warning(...)
except Exception as exc:
    logger.warning(...)
```

保存失败只记录 warning，不影响 `/chat` 和 `/chat/stream` 的响应。

### 面试可讲点

Agent 系统要区分核心依赖和增强能力。Trace 对排障很重要，但不应该因为日志落库失败而让用户请求失败。

## 11. 普通请求和流式请求都要保存 Trace

### 现象

`/chat` 和 `/chat/stream` 走的是两条不同执行路径：

```text
/chat         -> run()
/chat/stream  -> stream()
```

如果只在普通接口里保存 trace，流式接口的工具调用和反思过程就不会落库。

### 原因

AI 应用中流式响应通常有独立控制流，很多横切能力容易只接入一条路径。

### 解决方案

在两条路径的最终答案生成后都调用：

```python
trace_store.save_agent_state(state)
```

### 面试可讲点

日志、计费、trace、feedback 等能力必须覆盖普通接口和流式接口，否则线上排查时会出现大量“查不到链路”的请求。

## 12. Tool Calls 必须通过 `trace_id` 串起来

### 现象

只保存最终答案无法解释 Agent 为什么这么回答，也无法知道：

```text
调用了哪些工具
检索 query 是什么
工具是否成功
每个工具耗时多少
失败原因是什么
```

### 原因

Agent 的可解释性主要来自中间步骤，而不是最终文本。

### 解决方案

每个工具调用都写入 `tool_calls` 表，并带同一个 `trace_id`：

```python
ToolCall(
    trace_id=state.trace_id,
    name=item.name,
    arguments=item.arguments,
    output_summary=item.output_summary,
    success=item.success,
    latency_ms=item.latency_ms,
)
```

### 面试可讲点

`trace_id` 是贯穿一次请求的主线。通过它可以把用户问题、检索、工具调用、反思和最终答案串起来，实现 Agent 决策链路回放。

## 13. 用 JSONB 保存 Agent 中间状态快照

### 现象

`citations` 和 `reflections` 是结构化数据，但字段变化比较快：

```text
citation: chunk_id, score, metadata, source
reflection: passed, reason, followup_queries
```

### 原因

如果在早期就拆成很多关系表，开发成本较高，schema 也会频繁变动。

### 解决方案

在 PostgreSQL 中使用 `JSONB` 保存快照：

```python
citations = mapped_column(JSONB, nullable=True)
reflections = mapped_column(JSONB, nullable=True)
```

同时把需要统计和查询的字段单独结构化，例如：

```text
trace_id
tool_name
success
latency_ms
created_at
```

### 面试可讲点

Agent 中间状态适合先用 JSONB 保存完整快照，保证可回放；对需要聚合分析的核心字段再单独建列，兼顾灵活性和可查询性。

## 14. Trace 查询接口出现循环导入

### 现象

新增 `/traces` 查询接口后，直接调用 `trace_store` 时出现：

```text
ImportError: cannot import name 'trace_store' from partially initialized module
```

### 原因

`trace_store.py` 为了类型标注导入了 `AgentState`：

```python
from app.services.agent.state import AgentState
```

但 `app.services.agent.__init__` 会导入 orchestrator，orchestrator 又会导入 `trace_store`，形成循环导入：

```text
trace_store -> agent package -> orchestrator -> trace_store
```

### 解决方案

使用 `TYPE_CHECKING`，让类型导入只发生在静态类型检查阶段，不在运行时触发：

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.agent.state import AgentState

def save_agent_state(self, state: "AgentState") -> None:
    ...
```

### 面试可讲点

Python 项目拆模块后很容易出现循环导入。类型标注不应该引入运行时依赖，可以用 `TYPE_CHECKING` 和字符串注解解决。

## 15. Async API 中直接执行同步数据库查询

### 现象

`/traces` 是 async FastAPI 接口，但底层 SQLAlchemy engine 是同步的。如果直接在 async endpoint 中调用同步数据库查询，可能阻塞事件循环。

### 原因

项目当前使用的是同步 SQLAlchemy engine：

```python
engine = create_engine(...)
SessionLocal = sessionmaker(...)
```

而 FastAPI endpoint 是：

```python
async def list_traces(...):
    ...
```

同步 I/O 如果直接放在 async 函数中，会占住 event loop。

### 解决方案

使用 Starlette 的线程池工具执行同步查询：

```python
from starlette.concurrency import run_in_threadpool

return await run_in_threadpool(trace_store.list_traces, limit)
```

### 面试可讲点

异步 Web 服务里要注意阻塞操作。要么使用 async database driver 和 async SQLAlchemy，要么把同步 I/O 放进线程池，避免拖慢整个事件循环。

## 16. 数据库连接超时要快速暴露

### 现象

Docker Desktop 停止后，PostgreSQL 端口不可达，查询会等待很久：

```text
psycopg.errors.ConnectionTimeout: connection timeout expired
```

### 原因

数据库容器停止后，`127.0.0.1:15432` 不再监听。默认连接超时较长，会让 API 或脚本等待过久。

### 解决方案

将数据库连接地址改为明确的 IPv4，并增加短连接超时：

```text
postgresql+psycopg://agent:agent@127.0.0.1:15432/agent?connect_timeout=5
```

同时在 trace 查询接口中捕获数据库异常，返回明确的 503：

```python
raise HTTPException(status_code=503, detail="trace database unavailable")
```

### 面试可讲点

外部依赖不可用时，系统应该快速失败并返回清晰错误，而不是长时间挂起。连接超时、健康检查和错误码设计都属于可运维性的一部分。

## 17. Feedback 不能脱离 Trace 独立存在

### 现象

新增用户反馈接口时，如果允许任意 `trace_id` 写入反馈，就可能出现反馈数据无法关联到任何 Agent 请求。

### 原因

反馈的价值在于反向优化某一次具体回答。如果没有对应的 `chat_tasks.trace_id`，就无法回看当时的问题、证据、工具调用和反思过程。

### 解决方案

提交反馈前先检查 trace 是否存在：

```python
task_exists = session.execute(
    select(ChatTask.trace_id).where(ChatTask.trace_id == payload.trace_id)
).scalar_one_or_none()

if task_exists is None:
    return None
```

接口层将这种情况返回为：

```text
404 trace not found
```

### 面试可讲点

反馈数据必须和可回放的 Agent trace 绑定，才能用于后续误召回分析、rerank 优化、prompt 优化和评测集构造。

## 18. Feedback 接口也要处理数据库不可用

### 现象

当前 Docker Desktop 停止时，PostgreSQL 的 `127.0.0.1:15432` 不可达：

```text
TcpTestSucceeded = False
```

如果 feedback 接口不处理数据库异常，请求会表现成不清晰的 500 或等待超时。

### 原因

Feedback、Trace 查询都依赖 PostgreSQL，而 PostgreSQL 是外部服务。

### 解决方案

Feedback API 捕获 SQLAlchemy 异常并返回明确的 503：

```python
except SQLAlchemyError as exc:
    raise HTTPException(status_code=503, detail="trace database unavailable") from exc
```

同时继续使用 `run_in_threadpool` 包装同步数据库操作。

### 面试可讲点

反馈系统属于闭环优化能力，重要但不应该模糊失败原因。外部依赖不可用时，接口应该快速返回明确状态，便于前端和运维判断。

## 19. Feedback Rating 要做输入约束

### 现象

如果不限制评分范围，用户可能提交无效评分，例如 `0`、`10` 或负数，后续统计平均分会失真。

### 原因

API 边界层缺少输入约束会污染数据库。

### 解决方案

在 Pydantic schema 中限制评分范围：

```python
rating: int = Field(ge=1, le=5)
```

### 面试可讲点

用户反馈会进入后续评测和优化闭环，因此要在 API 层保证数据质量。越靠近入口做校验，后面数据治理成本越低。

## 20. 离线评测不能返回假指标

### 现象

早期 `app/eval/metrics.py` 是占位实现，即使没有真正跑检索，也会返回：

```text
Recall@5 = 0.0
MRR@10 = 0.0
CitationAccuracy = 0.0
ToolSuccessRate = 0.0
```

### 原因

评测接口还没有接入真实检索链路，只是为了占位展示指标名称。

### 解决方案

将评测改成读取 JSONL 评测集，并调用当前真实检索链路：

```text
knowledge_search = BM25 + ES 原生 kNN + CrossEncoder rerank
```

然后计算：

```text
Recall@5
MRR@10
CitationAccuracy
ToolSuccessRate
```

如果 ES 不可用，不再返回假指标，而是抛出依赖错误，由 API 返回：

```text
503 eval dependency unavailable
```

### 面试可讲点

评测指标必须来自真实链路，否则没有优化意义。依赖不可用时应该明确失败，而不是返回容易误导的假结果。

## 21. 评测集必须使用真实 Chunk ID

### 现象

原始评测集使用的是 demo chunk：

```text
demo_0000
demo_0001
```

这些 id 并不存在于当前 ES 索引中。

### 原因

项目早期还没有完成真实 chunk 和向量入库，所以评测集只是临时占位。

### 解决方案

将评测集替换为 RFC 数据集中的真实问题和真实 gold chunk id，例如：

```json
{
  "question": "What does HTTP status code 404 mean?",
  "gold_chunk_ids": [
    "rfc9110-http-semantics_c0760",
    "rfc9110-http-semantics_c0958"
  ]
}
```

并用本地 `rfc_parent_child_chunks.jsonl` 检查 gold chunk id 是否存在。

### 面试可讲点

RAG 评测集不只是写几个问题，还要把问题和可验证的证据 chunk 对齐。这样 Recall 和 MRR 才能真实反映检索效果。

## 22. 评测辅助函数也要保持一致的默认路径

### 现象

`run_eval()` 有默认数据集路径，但单独调用 `load_dataset()` 时报错：

```text
TypeError: load_dataset() missing 1 required positional argument: 'dataset_path'
```

### 原因

顶层评测函数和底层加载函数的默认参数不一致，导致单独测试加载逻辑不方便。

### 解决方案

给 `load_dataset()` 也加上同样的默认路径：

```python
def load_dataset(dataset_path: Path = Path("app/eval/dataset.jsonl")) -> list[dict]:
    ...
```

### 面试可讲点

评测工具本身也需要良好的开发体验。底层函数可单独测试，能降低排查成本。

## 23. 只记录 Tool Calls 不足以回放检索链路

### 现象

此前 `tool_calls` 表能记录：

```text
工具名
参数
是否成功
耗时
输出摘要
```

但它不能完整回答：

```text
这次检索返回了哪些 chunk？
这些 chunk 的分数是多少？
rerank 后的 top-k 是什么？
一次 Agent 请求中发生了几次检索？
```

### 原因

`tool_calls` 更适合记录工具级别的调用信息，而检索事件有自己的结构化字段，直接塞进 `output_summary` 会丢失可分析性。

### 解决方案

新增 `retrieval_events` 表，按 `trace_id` 记录每次检索：

```text
trace_id
query
top_k
retrieved_chunk_ids
scores
latency_ms
created_at
```

Agent 运行态也增加：

```python
retrieval_events: list[RetrievalEventRecord]
```

在 `knowledge_search` 工具成功后采集：

```python
RetrievalEventRecord(
    query=...,
    top_k=...,
    retrieved_chunk_ids=[...],
    scores=[...],
    latency_ms=...,
)
```

### 面试可讲点

Agent trace 不应该只存“调用了工具”，还要记录关键工具的领域事件。对 RAG 来说，检索事件是最重要的中间状态之一，可以用于误召回分析、评测对齐和检索优化。

## 24. Trace API 要返回 Retrieval Events

### 现象

如果 `retrieval_events` 只落库，但 `/traces/{trace_id}` 不返回，排查时仍然需要手动查数据库。

### 原因

Trace 的目标是让一次 Agent 决策链路可回放。API 返回内容必须覆盖任务、工具、检索、反思和引用证据。

### 解决方案

在 `TraceDetail` schema 中新增：

```python
retrieval_events: list[TraceRetrievalEvent]
```

`trace_store.get_trace()` 查询同一个 `trace_id` 下的 retrieval events，并随 trace 详情一起返回。

### 面试可讲点

可观测性不只是把数据写进库，还要提供可访问的回放入口。这样前端、调试脚本和评测工具都可以基于同一个 trace API 工作。

## 25. 检索事件和工具调用要避免职责混淆

### 现象

`knowledge_search` 本身既是一个工具调用，又包含具体的检索结果。如果只设计一张表，很容易字段越来越混乱。

### 原因

工具调用关注“执行过程”，检索事件关注“检索结果”。两者粒度不同。

### 解决方案

拆成两类记录：

```text
tool_calls:
  记录工具执行状态、参数、耗时、错误摘要

retrieval_events:
  记录 query、top_k、chunk ids、scores、检索耗时
```

两者通过同一个 `trace_id` 关联。

### 面试可讲点

这是可观测性建模的取舍：通用调用日志和领域事件日志分开存，既保留统一链路，又方便针对 RAG 检索做专项分析。

## 26. 需要统一健康检查定位外部依赖问题

### 现象

开发过程中经常需要判断：

```text
是代码问题？
还是 ES / Redis / PostgreSQL 没启动？
```

如果只看接口报错，很容易误判。

### 原因

RAG Agent 依赖多个外部服务：

```text
Elasticsearch: 检索和向量索引
Redis: session memory
PostgreSQL: trace、tool_calls、feedback
```

任何一个服务停止，都会影响某一部分能力。

### 解决方案

新增 `/health` 接口，统一返回：

```text
api
elasticsearch
redis
postgresql
```

每个依赖包含：

```text
status
detail
latency_ms
```

整体状态：

```text
ok: 所有依赖正常
degraded: 至少一个依赖不可用
```

### 面试可讲点

健康检查是可运维性的基础。它能把“环境没启动”和“业务代码错误”区分开，减少排障成本，也方便后续接入监控。

## 27. 健康检查要快速失败

### 现象

最初健康检查在 Docker 未启动时耗时较长：

```text
ES 约 9 秒
Redis 约 4 秒
PostgreSQL 约 5 秒
```

### 原因

外部依赖不可达时，如果不设置短超时，连接会等待系统默认超时。

### 解决方案

增加统一配置：

```text
DEPENDENCY_CHECK_TIMEOUT_SECONDS=2
```

ES 使用短 request timeout：

```python
AsyncElasticsearch(..., request_timeout=settings.dependency_check_timeout_seconds)
```

Redis 使用 `asyncio.wait_for`：

```python
await asyncio.wait_for(redis.ping(), timeout=...)
```

PostgreSQL 连接串使用：

```text
connect_timeout=2
```

### 面试可讲点

健康检查接口可能被频繁调用，不能因为依赖不可用而挂很久。快速失败能提升可观测性和系统响应稳定性。

## 28. Child Chunk 直接生成答案会出现半截文本

### 现象

早期 deterministic answer generator 直接截断 child chunk，回答里可能出现半截单词或不完整句子，例如 chunk 因滑窗 overlap 从句子中间开始。

### 原因

Child chunk 的目标是精确召回，不是直接面向用户展示。它可能为了保证召回粒度而牺牲上下文完整性。

### 解决方案

生成答案时优先使用 `parent_id` 找到 parent context，在 parent context 中做句子级抽取：

```text
child chunk: 用于召回和定位
parent chunk: 用于提供完整上下文和生成答案
```

具体做法：

```text
1. 从 parent context 切分句子
2. 根据问题关键词给句子打分
3. 选择最高分的 1-2 个完整句子
4. 没有 parent context 时再退回 child chunk 摘要
```

### 面试可讲点

父子 chunk 的价值就在于“子 chunk 负责召回，父 chunk 负责上下文”。这样可以同时兼顾检索精度和答案可读性。

## 29. 不依赖 LLM 时也可以做可解释答案生成

### 现象

当前项目阶段没有接入真实 LLM，但仍然需要给出可演示的答案。

### 原因

如果直接把 top-k chunk 拼出来，效果像检索结果列表，不像 Agent 回答；但接 LLM 又会引入 API key、成本和不确定性。

### 解决方案

实现 deterministic extractive answer：

```text
从证据上下文中抽取相关句子
保留 chunk_id、section、source_file 引用
输出 confidence
记录 evidence notes
```

confidence 规则：

```text
无证据 -> low
有证据但 reflection 未通过 -> medium
有证据且 reflection passed -> high
```

### 面试可讲点

在工程复现阶段，可以先做 deterministic answer generator，把检索、证据、引用和 trace 闭环跑通。后续再替换成 LLM Generator，风险更可控。

## 30. 消融实验需要复用同一条检索链路

### 现象

如果为了评测单独写一套 BM25、Vector 或 Hybrid 检索逻辑，容易和线上 `knowledge_search` 行为不一致。

### 原因

评测的目标是比较真实系统模块的贡献。如果评测链路和实际 Agent 工具链路不一致，指标就不能代表线上行为。

### 解决方案

给 `KnowledgeSearchInput` 增加配置开关：

```text
retrieval_mode = bm25 | vector | hybrid
use_rerank = true | false
use_metadata_adjustment = true | false
```

评测和 Agent 都复用同一个 `knowledge_search` 工具，只是评测时传入不同配置。

### 面试可讲点

消融实验应该在真实链路上做，而不是另写一套评测专用逻辑。这样才能说明 BM25、向量召回、rerank、metadata adjustment 对实际系统的贡献。

## 31. Rerank 需要候选集，不能只取最终 Top-K

### 现象

如果检索阶段只返回 `top_k` 个候选，再做 rerank，rerank 的作用会很有限。

### 原因

Rerank 是排序器，不是召回器。它需要一个比最终结果更大的候选集，才能把更相关的证据提到前面。

### 解决方案

当 `use_rerank=True` 时，先扩大候选数：

```python
candidate_k = max(payload.top_k * 8, 20)
```

然后：

```text
retriever 返回 candidate_k
reranker 从 candidate_k 中选最终 top_k
```

当 `use_rerank=False` 时，只返回原始检索 top_k。

### 面试可讲点

召回和精排是两阶段架构。召回阶段要保证候选覆盖，精排阶段才有空间提升 MRR 和首条引用准确率。

## 32. 默认消融配置要覆盖关键模块

### 现象

如果只跑一个默认配置，就看不出每个模块的贡献。

### 原因

系统包含多个可拆模块：

```text
BM25
Vector kNN
Hybrid fusion
CrossEncoder rerank
Metadata adjustment
```

需要逐步打开这些模块，观察指标变化。

### 解决方案

默认消融实验包含 5 组：

```text
bm25_only
vector_only
hybrid_no_rerank
hybrid_rerank
hybrid_rerank_metadata
```

每组在同一份 dataset 上计算：

```text
Recall@5
MRR@10
CitationAccuracy
ToolSuccessRate
```

### 面试可讲点

这能证明不是简单堆模块，而是用实验验证每个模块是否真的有效。比如 Hybrid 主要看 Recall，Rerank 主要看 MRR 和 CitationAccuracy。

## 33. 依赖不可用时不跑消融指标

### 现象

当前本地 `127.0.0.1:9200` 不可达：

```text
TcpTestSucceeded = False
```

### 原因

Elasticsearch 是 Docker 外部依赖，Docker 未运行时无法执行真实检索。

### 解决方案

不伪造消融结果。评测接口继续在依赖不可用时返回明确的 503：

```text
eval dependency unavailable
```

### 面试可讲点

评测结果必须可信。依赖不可用时应该显式失败，而不是返回 0 或假指标，否则会误导后续优化判断。

## 34. 评测结果需要可读报告，而不只是 JSON

### 现象

`/eval/run` 返回的是结构化 JSON，适合程序消费，但不适合面试展示或人工复盘。

### 原因

消融实验结果包含多组配置、多个指标和 case 明细。直接看 JSON 不直观，也不方便放进项目文档。

### 解决方案

新增报告脚本：

```text
scripts/run_eval_report.py
```

输出：

```text
reports/eval_report.md
```

报告包含：

```text
数据集规模
运行耗时
消融配置指标表
每组 case 明细
未命中样本列表
依赖不可用时的说明和修复命令
```

### 面试可讲点

评测不只是算指标，还要让指标可读、可复盘、可展示。Markdown 报告适合放在仓库里，体现工程交付完整性。

## 35. 评测报告不能在依赖失败时生成假表格

### 现象

当前本地 ES 不可用时，如果强行生成指标表，就会让报告看起来像真实跑过实验。

### 原因

评测依赖真实检索链路，而检索依赖 Elasticsearch。ES 不可用时，任何 Recall/MRR 都没有意义。

### 解决方案

报告脚本捕获 `EvalDependencyError`，生成失败说明报告：

```text
Evaluation did not run because a required dependency was unavailable.
Elasticsearch is unavailable at localhost:9200.
```

并给出修复命令：

```powershell
docker compose up -d
python scripts/upgrade_db.py
python scripts/run_eval_report.py
```

### 面试可讲点

评测报告要诚实表达实验状态。依赖失败时生成清晰失败报告，比生成空指标或假指标更专业。

## 36. 本地化错误信息会影响报告可读性

### 现象

Windows 环境下异常信息包含中文，本地 PowerShell 显示时可能出现乱码。

### 原因

底层异常来自系统本地化消息，报告虽然用 UTF-8 写入，但不同终端显示编码可能不一致。

### 解决方案

在报告中将常见依赖错误归一化为简短英文说明：

```text
Elasticsearch is unavailable at localhost:9200.
Redis is unavailable at localhost:6379.
PostgreSQL is unavailable at 127.0.0.1:15432.
```

### 面试可讲点

面向展示和交付的报告应该尽量稳定、清晰，避免把底层系统的本地化错误原样暴露给读者。

## 37. 消融评测结果没有获得时必须先排查依赖和索引

### 现象

虽然已经实现了 `/eval/run` 和 `scripts/run_eval_report.py`，但一开始没有拿到真实 Recall、MRR 等评测结果。

### 原因

评测依赖真实检索链路，而真实检索依赖：

```text
Elasticsearch 服务运行
agent_chunks 索引存在
索引中有已向量化的 child chunks
```

最近多次检查时：

```text
127.0.0.1:9200 TcpTestSucceeded = False
```

说明 Elasticsearch 没有运行，评测不能执行真实检索。

### 解决方案

按顺序排查：

```powershell
docker compose up -d
Invoke-RestMethod http://localhost:9200/_cluster/health
Invoke-RestMethod http://localhost:9200/agent_chunks/_count
```

如果索引不存在或为空，则重新入库：

```powershell
python scripts/index_chunks.py --input data/parsed/rfc_parent_child_chunks.jsonl --batch-size 64 --recreate
```

然后重新跑评测报告：

```powershell
python scripts/run_eval_report.py
```

### 面试可讲点

评测结果必须建立在真实可用的检索索引上。没有 ES 或索引为空时，不应该声称有指标提升，而应该先恢复依赖和数据。

## 38. Chunk 重新生成后 Gold Chunk ID 会失效

### 现象

启动 Docker、恢复 ES 后，第一次跑消融评测得到了较差结果：

```text
HTTP 404 问题没有命中原 gold chunk
heuristically cacheable 问题也没有命中原 gold chunk
```

但检查检索结果发现，系统返回的 chunk 实际上包含正确答案。

### 原因

后续优化 chunker 时收紧了 RFC 章节识别规则，并重新生成了 parent-child chunks。chunk id 随切分结果变化，导致旧评测集中的 gold chunk id 失效。

例如旧 gold：

```text
rfc9110-http-semantics_c0760
```

重新 chunk 后，HTTP 404 的正确证据变成：

```text
rfc9110-http-semantics_c0812
```

### 解决方案

用本地 `data/parsed/rfc_parent_child_chunks.jsonl` 检查 gold chunk 是否仍然对应正确证据，并更新评测集：

```text
What does HTTP status code 404 mean?
gold_chunk_ids = ["rfc9110-http-semantics_c0812"]

Which HTTP responses are heuristically cacheable?
gold_chunk_ids = ["rfc9110-http-semantics_c0749"]
```

然后重新运行：

```powershell
python scripts/run_eval_report.py --output reports/eval_report.md
```

### 面试可讲点

评测集和 chunk 策略是耦合的。只要重新切块，gold chunk id 就可能失效，因此需要版本化评测集，或者引入更稳定的 gold 标注方式，比如 section id / source span。

## 39. 当前消融实验结果显示 BM25 是强基线

### 现象

修复 gold chunk 后，真实消融结果如下：

```text
bm25_only:
  Recall@5 = 100.00%
  MRR@10 = 70.83%
  CitationAccuracy = 50.00%
  ToolSuccessRate = 100.00%

vector_only:
  Recall@5 = 50.00%
  MRR@10 = 54.17%
  CitationAccuracy = 50.00%
  ToolSuccessRate = 100.00%

hybrid_no_rerank:
  Recall@5 = 75.00%
  MRR@10 = 45.83%
  CitationAccuracy = 25.00%
  ToolSuccessRate = 100.00%

hybrid_rerank:
  Recall@5 = 100.00%
  MRR@10 = 55.00%
  CitationAccuracy = 25.00%
  ToolSuccessRate = 100.00%

hybrid_rerank_metadata:
  Recall@5 = 100.00%
  MRR@10 = 55.00%
  CitationAccuracy = 25.00%
  ToolSuccessRate = 100.00%
```

### 分析

当前评测集只有 4 条，而且问题偏 RFC 原文关键词型。BM25 对这种数据非常强，因此 hybrid / rerank 不一定超过 BM25。

相对 `bm25_only`：

```text
hybrid_rerank_metadata:
  Recall@5: +0.00 pp / +0.00%
  MRR@10: -15.83 pp / -22.35%
  CitationAccuracy: -25.00 pp / -50.00%
  ToolSuccessRate: +0.00 pp / +0.00%
```

相对 `hybrid_no_rerank`：

```text
hybrid_rerank:
  Recall@5: +25.00 pp / +33.33%
  MRR@10: +9.17 pp / +20.01%
  CitationAccuracy: +0.00 pp / +0.00%
  ToolSuccessRate: +0.00 pp / +0.00%
```

### 解决方案

报告脚本新增 baseline improvement 表，明确展示相对基线的百分点变化和相对百分比变化。

同时不把当前结果包装成“所有模块都有提升”，而是保留真实结论：

```text
Rerank 相比 hybrid_no_rerank 有提升
但当前小型关键词评测集上，BM25 是最强基线
metadata adjustment 在当前 4 条数据上没有额外提升
```

### 面试可讲点

消融实验的价值在于暴露真实效果，而不是证明预设结论。当前结果说明评测集需要扩充到更多语义改写、长尾和跨章节问题，才能更公平地验证向量召回和 rerank 的价值。

## 40. Agent 工具分发从硬编码升级为工具注册表

### 现象

早期 `ToolExecutor` 更接近根据 `tool_name` 做分支调用。这样在工具数量变多后会有几个问题：

- 工具名、参数 schema、超时策略分散在不同地方
- 新增工具容易忘记补充校验和观测信息
- 后续如果接入 LLM function calling，很难直接导出工具定义

### 处理

新增 `app/tools/registry.py`，用 `ToolSpec` 集中注册：

```text
name / description / input_model / handler / timeout_seconds / retry_count
```

`ToolExecutor` 统一从 registry 获取工具定义，然后用 Pydantic 做入参校验，再通过 `asyncio.wait_for` 执行工具。

### 面试可讲点

Agent 的工具调用不应该只是写几个 if-else。更工程化的做法是把工具抽象成可注册、可校验、可观测、可配置的 runtime。这样后续从 deterministic planner 升级到 LLM planner 时，不需要重写工具层。

## 41. 工具执行需要超时、重试和可读错误摘要

### 现象

RAG 工具依赖 ES、Redis、PostgreSQL、rerank 模型等外部或较重组件。如果某个工具卡住，Agent loop 会整体阻塞；如果异常字符串为空，trace 里也很难判断失败原因。

### 处理

在 `ToolSpec` 中加入 `timeout_seconds` 和 `retry_count`，执行时统一包一层：

```text
schema validate -> wait_for timeout -> retry -> record tool_call
```

同时给 `ToolExecutor` 增加 `_error_summary`，当异常 message 为空时记录异常类型，例如 `TimeoutError`。

### 面试可讲点

Agent 工程里最容易被忽略的是失败路径。工具可能慢、可能不可用、可能参数不合法，所以工具运行时必须具备超时、重试、结构化错误和 trace 记录，否则线上很难定位问题。

## 42. Planner 中文意图识别中发现编码损坏

### 现象

检查 `planner.py` 时发现中文关键词中有损坏字符串，例如原本应表示“方案”的位置出现乱码。这会导致中文问题无法被正确识别为 `plan_generation`。

### 处理

重写 `planner.py` 中的 `_classify` 规则，补充中文关键词：

```text
历史 / 上一轮 / 记忆 / 会话
比较 / 区别 / 差异 / 对比
步骤 / 流程 / 过程 / 如何
方案 / 设计 / 架构 / 规划
```

### 面试可讲点

中文项目里编码问题会直接影响规则系统、检索 query、评测集和日志。遇到乱码时不能只修表面显示，要检查它是否已经进入业务逻辑。本次问题会影响 Agent 的任务分类，因此需要修复代码并记录原因。

## 43. Agent 设计需要单独沉淀成文档

### 现象

代码里已经有 Planner、Executor、Reflector、Generator、Trace Store，但如果没有架构文档，面试时很难在短时间内讲清楚 Agent 的边界、执行流程和可扩展点。

### 处理

新增 `docs/agent_design.md`，用中文整理：

- Agent 执行流程
- 核心模块职责
- `AgentState` 设计
- 工具注册表设计
- 反思机制
- trace 和可观测性
- 当前限制与下一步升级方向

### 面试可讲点

项目不仅要能跑，还要能解释。文档化的价值是把“我写了几个接口”提升为“我设计了一套可追踪、可扩展、可评测的 Agent 架构”。

## 44. 当前目录不是 Git 工作树，不能用 git diff 做变更检查

### 现象

验证阶段执行：

```powershell
git diff -- app\services\agent\planner.py app\services\agent\executor.py app\tools\registry.py docs\agent_design.md docs\interview_debug_notes.md
```

返回：

```text
fatal: not a git repository (or any of the parent directories): .git
```

### 原因

当前项目目录 `C:\Users\junjie jiang\Desktop\agent` 没有 `.git` 元数据，因此不能用 Git 的 diff/status 来检查改动范围。

### 处理

改用更直接的验证方式：

- `python -m compileall app scripts` 检查 Python 语法和 import
- 运行一个不依赖 ES/Docker 的 `plan_generator` 工具执行测试
- 用 Python 读取文件内容，确认中文和关键章节确实写入

### 面试可讲点

工程验证不能只依赖 Git。对于本地从零搭建的项目，可能尚未初始化仓库，因此要准备替代检查方式：编译、单元级 smoke test、文件内容校验和接口级测试。

## 45. Multi-Agent 不能设计成多个角色随意聊天

### 现象

用户提出希望模仿 FastGPT 设计多 Agent 模式。这里容易走偏：只定义多个角色，例如 Router Agent、Retriever Agent、Writer Agent，然后让它们通过自然语言互相传话。

这种设计短期看起来像 multi-agent，但工程上很难回答：

- 状态在哪里保存
- 节点失败如何隔离
- 哪个 Agent 决定下一步
- 并行执行如何限制并发
- 如何定位一次失败来自路由、检索、反思还是生成

### 处理

新增 `docs/multi_agent_design.md`，明确采用 workflow / node / edge / runtime 的设计。

核心思路：

```text
Agent 是一种节点
Tool 是 Agent 内部能力
Workflow 是多个节点组成的 DAG
Runtime 负责调度、条件分支、并发、loop、trace 和失败隔离
```

### 面试可讲点

Multi-Agent 的价值不在于 Agent 数量，而在于把复杂任务拆成可观测、可评测、可恢复的结构化流程。借鉴 FastGPT 时应重点学习它的节点编排、输入输出、条件触发、并行执行和调试面板思想，而不是只复刻 UI。

## 46. Workflow MVP 先复用现有 trace 表，避免过早引入迁移风险

### 现象

Multi-Agent 设计中理想状态是新增 `workflow_runs` 和 `workflow_node_runs`，但当前项目已经有 `chat_tasks`、`tool_calls`、`retrieval_events` 和 `user_feedback`。如果第一步就加表，需要同步修改 SQLAlchemy model、迁移脚本、查询 API 和回归测试。

### 处理

MVP 先采用折中方案：

- 新增 `/workflows/run`
- API 响应中返回 `node_runs`
- 底层工具调用继续写入已有 `tool_calls`
- 检索事件继续写入已有 `retrieval_events`
- 最终答案仍通过 `trace_store.save_agent_state` 写入 `chat_tasks`

### 面试可讲点

多 Agent 的第一步不是把所有表都设计到位，而是先让运行时闭环跑通。已有 trace 表可以复用时，先复用能降低迁移风险；等 workflow node_run 字段稳定后，再引入专门表会更稳。

## 47. WorkflowDefinition 已定义 edges，但 Runtime MVP 先显式调度

### 现象

`app/services/workflow/definition.py` 中已经声明了 nodes 和 edges，例如：

```text
router -> retrieval
retrieval -> critic
critic -> answer / retrieval
```

但 `WorkflowRuntime` 第一版没有解释 condition 表达式，而是用显式 Python 分支执行 memory、plan、rag 三条主路径。

### 处理

这是有意的 MVP 切分：

- 先稳定 `WorkflowState`
- 先稳定 `WorkflowNodeRun`
- 先打通 Router / Retrieval / Critic / Answer
- 先提供 `/workflows/run`
- 下一步再实现通用 condition interpreter 和 DAG scheduler

### 面试可讲点

DAG runtime 最难的不是把边写进配置，而是正确处理条件判断、循环、失败恢复、并发和状态合并。MVP 中先显式调度，可以让业务链路先跑起来，同时保留 definition，为下一步通用调度器打基础。

## 48. PowerShell 管道中文输入会影响本地 smoke test

### 现象

用 PowerShell here-string 执行 Python smoke test 时，中文问题：

```text
请给出 Agent 架构方案
```

在测试输出中显示为：

```text
??? Agent ????
```

这导致 Router 没有识别到中文关键词“方案”，从而走了 RAG 分支，而不是 plan 分支。

### 处理

补跑英文 smoke test：

```text
Please design an agent architecture plan
```

验证结果为：

```text
router -> plan -> critic -> answer
tool_calls = plan_generator
```

### 面试可讲点

本地终端编码问题可能影响中文规则、query rewrite 和测试输入。真实 HTTP JSON 请求通常能保持 UTF-8，但命令行 smoke test 仍要注意编码；遇到中文路由异常时，要区分是业务逻辑问题还是测试输入已经损坏。

## 49. ES Async Client 生命周期还没有统一关闭

### 现象

运行 RAG workflow smoke test 后，进程退出时出现：

```text
Unclosed client session
Unclosed connector
```

### 原因

`HybridRetriever` 内部直接创建 `AsyncElasticsearch` client，但项目还没有统一的 application lifespan 或 client manager 来关闭异步连接。

### 处理

本轮没有重构客户端生命周期，因为 multi-agent MVP 的目标是先打通 workflow runtime。当前通过 plan 分支和 API smoke test 验证核心功能；ES client 关闭问题记录为后续基础设施优化。

### 面试可讲点

异步客户端要有生命周期管理。FastAPI 项目里更好的做法是在 lifespan startup 初始化共享 client，在 shutdown 调用 close，避免连接泄漏和测试退出 warning。

## 50. 检查不存在的 app/core/clients.py 暴露出客户端管理缺口

### 现象

排查 ES client 生命周期时尝试读取：

```powershell
Get-Content app\core\clients.py
```

返回文件不存在。

### 处理

确认当前项目没有集中式 client manager。短期不阻塞 workflow MVP，长期建议新增 `app/core/lifespan.py` 或 `app/core/clients.py` 管理 ES / Redis / PostgreSQL 连接生命周期。

### 面试可讲点

这个问题说明项目从功能骨架走向生产化时，需要把“能调用外部服务”升级为“能管理外部服务生命周期”。这也是 Agent 系统工程化的一部分。

## 51. 8000 端口已有服务但不是当前新代码

### 现象

验证新接口时发现 8000 端口已经有进程监听，但请求：

```text
POST http://127.0.0.1:8000/workflows/run
GET  http://127.0.0.1:8000/health
```

都返回 404。

### 原因

端口监听不等于当前项目服务已经加载。可能是旧版本 uvicorn、其他应用，或者之前启动的进程没有热加载新路由。

### 处理

没有强行杀掉 8000 端口进程，而是在 8010 启动当前项目：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

随后验证：

```text
GET  /health -> 200
POST /workflows/run -> 200
GET  /traces/{trace_id} -> 能读取刚才 workflow 产生的 trace
```

### 面试可讲点

本地端口可用性和服务版本是两个问题。验证新接口时不能只看端口是否监听，还要请求具体路由确认当前代码是否已经加载。

## 52. Multi-Agent MVP 验证结果

### 结果

新接口：

```text
POST /workflows/run
```

请求：

```json
{
  "question": "Please design an agent architecture plan",
  "session_id": "http_smoke",
  "top_k": 3
}
```

返回的节点链路：

```text
router -> plan -> critic -> answer
```

返回的工具调用：

```text
plan_generator success=true output_summary="returned 4 plan items"
```

并且通过：

```text
GET /traces/{trace_id}
```

确认底层 `tool_calls` 已经持久化到 PostgreSQL。

### 面试可讲点

这个 MVP 已经证明 multi-agent 不是停留在文档层：它有独立的 workflow API、有节点级运行记录、有底层工具调用、有 trace 持久化。下一步要补的是通用 DAG condition interpreter、node_run 持久化和并行节点。

## 53. Workflow node_runs 持久化落库

### 现象

上一版 multi-agent MVP 的 `node_runs` 只存在于 API 响应中，刷新后无法单独查询 workflow 的节点执行过程。这不符合 FastGPT 类 workflow 调试面板的需求。

### 处理

新增两张表：

```text
workflow_runs
workflow_node_runs
```

并新增：

```text
GET /workflows/{workflow_run_id}
```

用于查询一次 workflow 的节点运行记录、工具调用和最终答案。

### 验证

运行：

```text
POST /workflows/run
GET  /workflows/{workflow_run_id}
```

结果可以查回：

```text
router -> plan -> critic -> answer
router -> retrieval -> critic -> answer
```

### 面试可讲点

Multi-Agent 系统必须能解释每个 Agent 的输入、输出、耗时和状态。只保存最终答案是不够的；node_runs 持久化后，才能做失败定位、链路回放和节点级评测。

## 54. DAG condition interpreter 不能直接使用 eval

### 现象

WorkflowDefinition 中有条件边：

```text
task_type == 'plan_generation'
passed == false and max_iterations_reached == false
task_type in ['document_qa', 'procedure_query', 'compare', 'out_of_scope']
```

最简单的实现方式是直接 `eval(condition)`，但这会引入代码执行风险。

### 处理

实现了一个小型白名单表达式解释器，只支持当前 workflow 需要的语法：

```text
==
in
and
or
true / false
string literal
list literal
```

变量也只允许从 `WorkflowState.variables` 和受控字段中读取。

### 面试可讲点

Workflow condition 是用户配置化能力的入口，不能直接执行任意 Python 表达式。生产系统里要做 DSL 白名单、schema 校验和权限隔离。本项目 MVP 用小解释器替代 `eval`，体现了安全边界意识。

## 55. Workflow Runtime 从显式分支升级为边驱动调度

### 现象

上一版 runtime 中存在：

```text
if route == "memory"
elif route == "plan"
else retrieval
```

这能跑通 MVP，但 workflow definition 中声明的 edges 没有真正参与调度。

### 处理

Runtime 改为：

```text
从第一个 node 开始执行
根据 outgoing edges 找可通过的 condition
推进到下一个 node
critic -> retrieval 时增加 iteration
到 answer 后结束
```

如果某个节点同时命中多个后继节点，MVP 先报错，因为 parallel/merge 尚未实现。

### 面试可讲点

这一步把 workflow 从“写死流程”推进到“由图定义驱动流程”。后续要支持并行时，只需要扩展多后继节点的调度策略，而不是重写业务节点。

## 56. 中断后的验证恢复

### 现象

RAG workflow HTTP 验证过程中，用户主动中断了一次命令。中断可能导致请求已经发出但结果没有显示，也可能导致本地验证状态不完整。

### 处理

恢复后没有假设结果成功，而是重新检查：

```text
GET /health
python -m compileall app scripts
POST /workflows/run
GET /workflows/{workflow_run_id}
```

最终确认：

```text
NODES=router,retrieval,critic,answer
TOOLS=knowledge_search,parent_context
CITATIONS=3
DETAIL_STATUS=success
```

### 面试可讲点

长流程开发里命令被中断很常见。恢复时要重新验证服务状态、代码编译和关键接口结果，不能根据中断前的半截输出推断成功。

## 57. Parallel Retrieval 不能共享同一个 AgentState 写 evidence

### 现象

为了模仿 FastGPT Parallel Run，需要让 RAG 路径同时执行两个检索分支：

```text
retrieval_original
retrieval_rewritten
```

如果两个分支直接并发写同一个 `AgentState.evidence`，会带来几个问题：

- evidence 顺序不稳定
- parent_context 可能交错写入
- tool_calls 和 retrieval_events 难以区分来自哪个分支
- merge 阶段无法判断去重前的分支贡献

### 处理

每个 retrieval 分支使用 `agent_state.model_copy(deep=True)` 创建 branch state：

```text
branch_state.evidence = []
branch_state.parent_contexts = {}
branch_state.tool_calls = []
branch_state.retrieval_events = []
```

分支执行完后只把结构化输出写入 `node_outputs`，再由 `merge_evidence` 统一：

```text
去重 -> 按 score 排序 -> 截断 top_k -> 写回主 AgentState
```

### 验证

HTTP 验证结果：

```text
NODES=router,retrieval_original,retrieval_rewritten,merge_evidence,critic,answer
TOOLS=knowledge_search,parent_context,knowledge_search,parent_context
CITATIONS=3
```

数据库验证：

```text
workflow_node_runs:
router success
retrieval_original success
retrieval_rewritten success
merge_evidence success
critic success
answer success
```

### 面试可讲点

并行 Agent 的难点不是 `asyncio.gather`，而是状态隔离和结果合并。每个分支应该有自己的局部状态，主状态只在 merge 节点统一更新，这样结果可复现、可解释、可评测。

## 58. Workflow Streaming 需要事件队列，而不是在深层函数里直接 yield

### 现象

实现 `POST /workflows/stream` 时，节点执行发生在 `_run_graph` 和 `_run_node` 内部。如果直接在这些深层函数里 `yield`，会破坏普通 `run()` 和 streaming 两种调用方式的复用。

### 处理

采用 `asyncio.Queue` 做事件通道：

```text
stream() 创建 queue
runner task 执行 workflow
_run_node 通过 emit callback 把事件写入 queue
stream() 从 queue 中 yield SSE event
```

这样普通 `run()` 不传 `emit`，行为保持不变；`stream()` 传入 `emit`，就能实时得到：

```text
workflow_start
node_start
node_done
workflow_done
```

### 面试可讲点

Streaming 不应该和业务执行逻辑强耦合。用事件回调和队列可以把“执行”和“传输”解耦，后续同一套事件既可以输出 SSE，也可以写 WebSocket、日志或调试面板。

## 59. PowerShell Invoke-WebRequest 读取 SSE 出现客户端空引用

### 现象

用 PowerShell 测试：

```powershell
Invoke-WebRequest -Method Post -Uri http://127.0.0.1:8013/workflows/stream ...
```

出现：

```text
Object reference not set to an instance of an object.
```

### 判断

随后用 FastAPI `TestClient` 测试同一个 `/workflows/stream`，返回 200，并看到标准 SSE：

```text
event: workflow_start
data: {...}

event: node_start
data: {...}

event: node_done
data: {...}
```

同时普通 `/workflows/run` 仍能正常返回，因此判断这是 PowerShell 客户端读取流式响应的问题，不是服务端路由或 runtime 问题。

### 处理

使用 `TestClient.stream()` 验证 SSE 服务端输出格式。

### 面试可讲点

流式接口测试时要区分服务端问题和客户端工具问题。SSE/WebSocket 这类长连接接口，用通用 HTTP 命令有时会误报，需要换成更贴近协议的测试方式。

## 60. RAG Streaming 验证了并行节点的事件顺序

### 结果

RAG streaming service 层验证得到：

```text
workflow_start
node_start router
node_done router
node_start retrieval_original
node_start retrieval_rewritten
node_done retrieval_original
node_done retrieval_rewritten
node_start merge_evidence
node_done merge_evidence
node_start critic
node_done critic
node_start answer
node_done answer
workflow_done
```

### 面试可讲点

并行节点在事件流中不应表现成完全线性的“一个结束再开始下一个”。两个 retrieval 节点连续 start，随后分别 done，说明 runtime 真实执行了并行分支，也能被调试面板观察到。

## 61. LLM 接入必须保留 deterministic 降级

### 现象

接入 LLM Planner、LLM Critic、LLM Answer Generator 时，如果直接替换 deterministic 节点，会让本地开发强依赖外部 API key 和网络。一旦没有 key，整个 workflow 都无法测试。

### 处理

在 `WorkflowRequest` 中新增三个开关：

```text
use_llm_planner
use_llm_critic
use_llm_answer
```

默认都是 `false`。开启后才调用 LLM；否则继续走 deterministic Planner / Reflector / Generator。

### 面试可讲点

LLM 能力应该是增强层，不应该让系统失去可复现的基础路径。保留 deterministic fallback 可以支持本地调试、回归测试和无 API key 环境。

## 62. 不新增 OpenAI SDK，使用 httpx 做 OpenAI-compatible provider

### 现象

项目没有 `pyproject.toml`，依赖集中在 `requirements.txt`，其中已经有：

```text
httpx==0.28.1
```

如果新增 OpenAI SDK，会引入额外依赖和版本管理成本。

### 处理

新增 `app/services/llm.py`，实现：

```text
LLM_PROVIDER=mock
LLM_PROVIDER=openai
LLM_PROVIDER=openai-compatible
```

真实 provider 使用 HTTP 调用：

```text
POST {LLM_BASE_URL}/chat/completions
```

请求体包含：

```text
model
messages
temperature
```

### 面试可讲点

使用 OpenAI-compatible 抽象可以兼容 OpenAI、私有网关或其他兼容服务。底层使用 `httpx` 能减少依赖，同时保留超时、错误处理和 JSON 解析控制权。

## 63. Mock LLM 不能用完整 prompt 做路由判断

### 现象

第一次 mock LLM RAG 测试时，问题是：

```text
What does HTTP 404 mean?
```

但 workflow 被错误路由到了：

```text
router -> plan -> critic -> answer
```

### 原因

mock LLM 最初把 system prompt 和 user prompt 拼在一起做关键词判断。system prompt 中包含 `plan_generation`，导致普通 RAG 问题被误判为 plan_generation。

### 处理

修复 mock provider，只读取最后一条 user message 做 mock 路由判断。

修复后 RAG LLM mock 验证结果：

```text
router -> retrieval_rewritten -> retrieval_original -> merge_evidence -> critic -> answer
tool_calls = knowledge_search,parent_context,knowledge_search,parent_context
citations = 3
```

### 面试可讲点

Mock 不是随便写的假数据，它也是测试基础设施。Mock 如果污染了 system prompt，就会掩盖真实业务路径，导致测试结论失真。

## 64. LLM 输出必须按 JSON 解析并提供 fallback

### 现象

LLM Planner / Critic / Answer 都需要结构化输出。如果直接相信模型返回，可能遇到：

- 返回 Markdown fenced JSON
- 返回自然语言解释
- 缺字段
- 字段类型不对

### 处理

`llm_client.chat_json()` 统一处理：

```text
去掉 ```json fence
json.loads
失败时使用 fallback
```

各 LLM Agent 再对关键字段做白名单或类型检查。

### 面试可讲点

LLM 是不稳定组件，结构化输出必须有解析、校验和 fallback。否则 Agent 的控制流会被一次格式错误打断。

## 65. ES / Redis 客户端需要 FastAPI lifespan 统一关闭

### 现象

多次 RAG workflow smoke test 结束时出现：

```text
Unclosed client session
Unclosed connector
```

主要来自全局 `AsyncElasticsearch` client 没有在进程退出前关闭。

### 原因

项目里存在长生命周期客户端：

```text
app/services/retriever.py -> AsyncElasticsearch
app/services/memory.py    -> redis.asyncio client
app/db/session.py         -> SQLAlchemy engine
```

之前只有部分脚本手动执行：

```text
await retriever.client.close()
```

但 FastAPI 服务本身没有统一 shutdown 钩子，因此通过 API 或 TestClient 跑 RAG 链路后，ES async client 可能没有被关闭。

### 处理

新增：

```text
app/core/lifespan.py
```

提供：

```text
lifespan(app)
close_app_resources()
```

关闭逻辑：

```text
await retriever.close()
await session_memory.close()
engine.dispose()
```

并在 `app/main.py` 中：

```python
app = FastAPI(..., lifespan=lifespan)
```

### 验证

使用 FastAPI `TestClient` 上下文执行 RAG workflow：

```text
with TestClient(app) as client:
    POST /workflows/run
```

结果：

```text
status=200
nodes=router,retrieval_original,retrieval_rewritten,merge_evidence,critic,answer
citations=3
client closed
```

没有再出现 ES `Unclosed client session`。

直接调用 service 的脚本场景也验证：

```text
try:
    await workflow_service.run(...)
finally:
    await close_app_resources()
```

同样没有 unclosed warning。

### 面试可讲点

异步客户端生命周期是生产化必做项。服务型应用不能依赖脚本尾部手动 close，而应该用 FastAPI lifespan 管理 startup/shutdown。这样 API、TestClient、长期运行服务都能走统一资源回收路径。

## 66. 脚本侧也应复用统一 close 入口

### 现象

代码中还有几处脚本直接调用：

```text
await retriever.client.close()
```

虽然当前可用，但这会让脚本绑定 `HybridRetriever` 的内部实现。以后如果 retriever 改成 lazy client 或 client manager，脚本都要跟着改。

### 处理

新增：

```python
async def close(self) -> None:
    await self.client.close()
```

并把脚本统一改成：

```text
await retriever.close()
```

涉及：

```text
scripts/search_chunks.py
scripts/index_chunks.py
scripts/run_eval_report.py
```

### 验证

运行：

```powershell
python scripts/search_chunks.py "What does HTTP 404 mean?" --top-k 1 --no-rerank
```

返回正确检索结果：

```text
rfc9110-http-semantics_c0812
section=15.5.5. 404 Not Found
```

且没有 ES unclosed session warning。

### 面试可讲点

统一资源关闭入口能降低耦合。脚本不应该知道 retriever 内部是 `AsyncElasticsearch`，只需要调用 `retriever.close()`。

## 67. TestClient 必须用上下文管理器触发 lifespan

### 现象

如果写成：

```python
client = TestClient(app)
client.post(...)
```

测试结束时不一定能可靠触发 lifespan shutdown。

### 处理

生命周期相关测试统一写成：

```python
with TestClient(app) as client:
    client.post(...)
```

这样才能保证进入 startup，并在退出 `with` 时执行 shutdown。

### 面试可讲点

验证资源释放时，测试方式本身也很重要。对于 FastAPI lifespan，要用 TestClient 上下文管理器，否则可能误判服务端资源泄漏。

## 68. search_chunks --no-rerank 仍触发 HF 加载

### 现象

运行：

```powershell
python scripts/search_chunks.py "What does HTTP 404 mean?" --top-k 1 --no-rerank
```

虽然没有使用 rerank，但仍看到 Hugging Face 权重加载提示。

### 初步原因

`search_chunks.py` 顶部导入了：

```python
from app.tools.knowledge_search import KnowledgeSearchInput, knowledge_search
```

而 `knowledge_search` 模块会导入 reranker。即使运行时走 `--no-rerank` 分支，模块导入阶段也可能触发相关初始化。

### 处理

本轮目标是客户端生命周期管理，因此没有重构导入链；但已确认它不是 ES unclosed session 的来源。

### 面试可讲点

除了资源关闭，AI 项目还要注意 import side effect。模型加载应该尽量 lazy load，否则 CLI 工具即使不用某个模型，也可能因为模块导入而产生额外启动成本。

## 69. 关闭全局客户端后要能在同一进程内重建

### 现象

接入 FastAPI lifespan 后，`TestClient` 退出时会关闭全局 ES / Redis client。如果同一个 Python 进程里再次创建 `TestClient`，可能复用到已关闭 client。

这种情况在 pytest 或多轮 smoke test 中很常见。

### 处理

把 `HybridRetriever` 和 `SessionMemory` 改成 lazy client：

```text
_client = None
client property 第一次使用时创建
close() 后将 _client 置回 None
下一次使用自动重建
```

### 验证

同一个 Python 进程里连续运行两次：

```python
for i in range(2):
    with TestClient(app) as client:
        client.post("/workflows/run", ...)
```

结果两次都成功：

```text
0 200 ... citations=1
closed 0
1 200 ... citations=1
closed 1
```

且没有 ES unclosed session warning。

### 面试可讲点

生命周期管理不只是“退出时 close”，还要考虑测试和热重载场景下的重建能力。关闭后置空并 lazy recreate，是管理全局异步客户端的一种简单可靠方式。

## 70. 记忆系统拆成 Redis 短期记忆和 PostgreSQL 长期记忆

### 现象

原有记忆系统只有 Redis session messages：

```text
session:{session_id}:messages
```

它适合保存最近上下文，但不适合长期沉淀用户偏好、历史结论和面试准备信息。

### 处理

新增 PostgreSQL 表：

```text
long_term_memories
```

字段：

```text
session_id
memory_type
content
importance
source_trace_id
meta
created_at
```

保留 Redis 作为短期记忆，PostgreSQL 作为长期记忆。

### 面试可讲点

短期记忆和长期记忆的读写模式不同：短期记忆追求低延迟和自动过期，适合 Redis；长期记忆需要持久化、可查询、可审计，适合 PostgreSQL。

## 71. Workflow 自动沉淀 conversation_summary

### 现象

如果只提供手动写入长期记忆，系统不会自动从交互中学习，用户每次都要显式保存。

### 处理

在 workflow 完成写 Redis 短期记忆时，同时调用：

```text
session_memory.remember_interaction(...)
```

自动生成：

```text
User asked: ...
Assistant answered: ...
```

并写入 `long_term_memories`，类型为：

```text
conversation_summary
```

### 验证

运行 workflow 后查询：

```text
GET /memory/{session_id}
```

能看到自动生成的 `conversation_summary`。

### 面试可讲点

长期记忆不应该只靠用户手动保存。对话结束后自动沉淀 summary，可以形成可复用上下文；但生产里还需要加去重、隐私过滤和用户确认机制。

## 72. MemoryAgent 同时读取短期和长期记忆

### 现象

原来的 `memory_read` 只返回 Redis 最近消息，MemoryAgent 无法读取长期记忆。

### 处理

扩展 `memory_read` 输出：

```text
messages
long_term_memories
```

`ToolExecutor` 会把长期记忆追加为：

```text
role=long_term_memory
```

MemoryAgent node 输出拆分为：

```text
short_term_messages
long_term_memories
memory_messages
```

### 验证

运行：

```text
POST /memory
POST /workflows/run
question = What memory do you have about this session?
```

结果：

```text
router -> memory -> critic -> answer
tool_summary = returned 1 memory messages and 1 long-term memories
```

### 面试可讲点

MemoryAgent 不应该只读“最近聊天记录”，还应读取长期用户偏好和历史结论。短期 + 长期结合，才能支撑更真实的个性化 Agent。

## 73. JSONB 不能直接保存 datetime 对象

### 现象

MemoryAgent 读取长期记忆后，`node_runs.output` 中包含 `created_at: datetime`。保存 workflow node_runs 时出现：

```text
Object of type datetime is not JSON serializable
```

### 原因

PostgreSQL JSONB 需要 JSON-serializable 数据，Python `datetime` 不能直接写入。

### 处理

在 `TraceStore.save_workflow_state()` 写入 node input/output 前统一做 JSON-safe 转换：

```python
json.loads(json.dumps(value, default=str, ensure_ascii=False))
```

### 验证

重新运行 MemoryAgent workflow：

```text
router -> memory -> critic -> answer
GET /workflows/{workflow_run_id} -> 200
```

### 面试可讲点

Trace/NodeRun 这类可观测数据经常包含 datetime、Pydantic model、Decimal 等非原生 JSON 类型。写入 JSONB 前应该统一做序列化边界处理，而不是在每个业务节点里手动处理。

## 74. 长期记忆暂时不做向量化

### 现象

长期记忆也可以做向量检索，但这会引入新的 embedding、索引同步、删除更新和评测问题。

### 处理

MVP 先做：

```text
session_id 过滤
关键词 ilike 匹配
importance + created_at 排序
```

### 面试可讲点

不是所有记忆第一版都要上向量库。对于 session 级长期记忆，先用 PostgreSQL 做可审计、可解释的 MVP 更稳；当记忆规模和语义检索需求上来后，再引入向量化长期记忆。
## 75. API Key 鉴权默认关闭，生产可开启

### 现象

项目里有一些接口不应该完全公开，例如：

```text
POST /documents/upload
POST /eval/run
POST /memory
GET /traces
GET /workflows/{workflow_run_id}
```

这些接口涉及写入、评测、调试信息或 trace 数据。

### 处理

新增：

```text
REQUIRE_API_KEY
API_KEY
```

开启后通过 `X-API-Key` 校验，并使用 `hmac.compare_digest` 做常量时间比较。

### 验证

```text
POST /memory without key -> 401
POST /memory wrong key   -> 401
POST /memory right key   -> 200
GET /traces without key  -> 401
GET /traces right key    -> 200
```

### 面试可讲点

不是所有接口都应该同等公开。业务入口可以保持简单，但写入、评测、trace、debug 类接口至少要有基础 API Key 保护。

## 76. 工具权限按 scope 控制，默认禁用 external

### 现象

随着 LLM Planner 接入，未来 Planner 可能选择工具。如果工具没有权限边界，模型可能调用不该暴露的工具，例如外部搜索、文件操作或管理类工具。

### 处理

给 `ToolSpec` 增加：

```text
scope
```

当前映射：

```text
knowledge_search -> retrieval
parent_context   -> retrieval
memory_read      -> memory
plan_generator   -> planning
web_search       -> external
```

默认配置：

```text
ALLOWED_TOOL_SCOPES=retrieval,memory,planning
```

因此 `external` 默认不可用。

### 验证

设置：

```text
ALLOWED_TOOL_SCOPES=memory,planning
```

运行 RAG workflow，结果：

```text
knowledge_search:false:tool scope not allowed: retrieval
parent_context:false:tool scope not allowed: retrieval
```

workflow 返回降级答案，而不是执行检索。

### 面试可讲点

Agent 工具权限不能只靠 prompt 约束。工具注册表里必须有机器可执行的权限字段，执行器在真正调用前做强校验。

## 77. 工具禁用后要避免无意义多轮重试

### 现象

禁用 retrieval scope 后，RAG workflow 第一轮检索必然失败。如果 Critic 继续认为证据不足并触发 follow-up，会重复失败。

### 处理

Workflow state 增加：

```text
retrieval_allowed
```

当 retrieval 不允许且 reflection 不通过时，Critic 会设置：

```text
max_iterations_reached = true
```

这样只失败一轮并行检索，然后进入 answer 降级输出。

### 面试可讲点

权限拒绝和普通检索失败不是一类问题。权限拒绝不应该靠重试解决，应快速停止并返回可解释降级结果。

## 78. Workflow 和 Memory 请求增加输入约束

### 现象

如果不限制输入，用户可以传入超长 question、奇怪 session_id，影响日志、数据库索引、Redis key 和 trace 查询。

### 处理

新增：

```text
MAX_QUESTION_LENGTH
MAX_SESSION_ID_LENGTH
```

并限制：

```text
session_id / workflow_id / memory_type 只允许 a-zA-Z0-9_.:-
question / memory content 有最大长度
top_k 已限制在 1 到 20
```

### 面试可讲点

Agent 安全不只包括 LLM prompt injection，也包括普通 Web API 的输入边界。session_id 这种字段会进入 Redis key、数据库索引和日志，必须限制格式。

## 79. Workflow condition 继续保持白名单解释器

### 现象

权限与安全部分重新检查了 workflow condition。这里如果用 `eval`，workflow 配置就能执行任意 Python。

### 处理

继续使用已有的 condition 白名单解释器，只支持：

```text
==
in
and
or
true / false
string/list literal
```

### 面试可讲点

可配置 workflow 的条件表达式本质上是 DSL。DSL 的执行器必须是白名单解释器，而不是语言运行时。

## 80. Workflow 从硬编码迁移到 JSON 配置

### 现象

之前 `rag_multi_agent_v1` 的 nodes 和 edges 完全写在 Python 文件里。这样每次调整 workflow 都要改代码、重新部署，也不利于后续做可视化编辑器。

### 处理

新增：

```text
config/workflows/rag_multi_agent_v1.json
```

并重写 `app/services/workflow/definition.py`：

```text
内置 BUILTIN_RAG_MULTI_AGENT_V1
加载 config/workflows/*.json
JSON 同名配置覆盖内置配置
get_workflow_definition(workflow_id)
list_workflow_definitions()
reload_workflow_definitions()
```

### 面试可讲点

Workflow 的本质是配置驱动的 DAG，不应该长期硬编码在 Python 里。迁移到 JSON 后，业务编排和节点实现解耦，后续才能接可视化编辑、版本管理和灰度发布。

## 81. Workflow 配置必须校验边引用

### 现象

配置化后容易写出坏配置，例如：

```json
{"from_node": "router", "to_node": "missing"}
```

如果不在加载阶段校验，运行到一半才失败，会很难排查。

### 处理

加载时校验：

```text
workflow_id 非空
至少一个 node
node_id 不重复
edge.from_node 必须存在
edge.to_node 必须存在
max_iterations >= 1
```

### 验证

构造坏配置：

```text
to_node=missing
```

得到：

```text
ValueError edge references unknown to_node: missing
```

### 面试可讲点

配置化不是把 JSON 读进来就完了。配置必须尽早校验，把错误阻断在启动/加载阶段，而不是让用户请求跑到一半才失败。

## 82. 保留内置 fallback，避免配置文件损坏导致系统不可用

### 现象

如果完全依赖外部 JSON，文件缺失或损坏会导致默认 workflow 也不可用。

### 处理

保留：

```text
BUILTIN_RAG_MULTI_AGENT_V1
```

加载顺序：

```text
先注册内置 definition
再加载 config/workflows/*.json
同名配置覆盖内置
坏配置记录 warning 并跳过
```

### 面试可讲点

配置化也要考虑可用性。内置 fallback 能保证配置文件坏掉时，系统至少还有一个可运行的默认 workflow。

## 83. Workflow reload 接口需要鉴权

### 现象

`POST /workflows/reload` 会重新加载 workflow 配置，属于管理类操作。如果公开，会带来误操作风险。

### 处理

reload 接口复用 API Key 鉴权：

```text
POST /workflows/reload without key -> 401
POST /workflows/reload with key    -> 200
```

### 面试可讲点

动态 reload 是运维能力，也是一种管理权限。它不能和普通业务查询接口一样公开。
## 84. Parallel 策略从隐式 gather 升级为可配置策略

### 现象

之前 runtime 遇到多个后继节点时直接：

```python
asyncio.gather(...)
```

这能并行执行，但没有并发上限、失败策略和最小成功数。

### 处理

在 workflow node config 中新增：

```json
{
  "parallel_policy": {
    "max_concurrency": 2,
    "failure_strategy": "continue_on_error",
    "min_success": 1
  }
}
```

runtime 根据 policy 使用 `asyncio.Semaphore` 控制并发。

### 面试可讲点

并行不是简单 gather。生产里需要控制并发、防止雪崩，并定义部分失败时是继续、降级还是整体失败。

## 85. Merge 策略支持 source_nodes、top_k 和权重

### 现象

之前 `merge_evidence` 写死：

```text
source_nodes = retrieval_original, retrieval_rewritten
top_k = request.top_k
score = 原始 score
```

这不利于实验不同分支权重，也不利于后续增加更多检索分支。

### 处理

在 merge 节点 config 中新增：

```json
{
  "source_nodes": ["retrieval_original", "retrieval_rewritten"],
  "top_k_source": "request",
  "dedupe_key": "chunk_id",
  "score_weights": {
    "retrieval_original": 1.0,
    "retrieval_rewritten": 1.0
  }
}
```

merge 时按 `chunk_id` 去重，同一个 chunk 保留加权分数更高的版本，再按 score 排序截断。

### 面试可讲点

Merge 节点是多 Agent 系统的关键。不同分支的输出不能简单拼接，而要去重、排序、加权，并保留 source_nodes 方便归因。

## 86. continue_on_error 要记录失败分支 node_run

### 现象

测试部分失败时，构造一个不存在 handler 的分支：

```text
missing_handler
```

最初该分支被 `continue_on_error` 捕获，但没有写入 failed node_run，因为 `getattr(workflow_nodes, node_id)` 在 `_run_node` 的 try 之前。

### 处理

把 handler lookup 移入 `_run_node` 的 try 内部。

修复后：

```text
missing_handler:failed
retrieval_original:success
merge_evidence:success
```

### 面试可讲点

失败分支必须进入 trace。否则系统看起来“成功降级”，但调试面板里看不到哪个 Agent 失败，后续无法归因。

## 87. fail_fast 不能直接取消其他并行分支

### 现象

第一次测试 `fail_fast` 时，一个分支失败后 `asyncio.gather` 直接抛异常，另一个检索分支可能还没完成清理，导致：

```text
Unclosed client session
```

### 处理

将 fail_fast 改成 fail-after-join：

```text
所有已启动分支都收束
失败分支写入 node_run
如果 failure_strategy=fail_fast 且有失败，再整体失败
```

### 验证

`fail_fast` 仍返回 500，但不再出现 ES unclosed client warning。

### 面试可讲点

并行失败策略不仅是业务语义，也关系到资源清理。直接取消异步任务容易留下未关闭连接；等待分支收束后再失败更可观测、更安全。
## 88. Skill 设计参考 FastAPI Router，而不是直接暴露工具

### 现象

用户希望设计 Skill 和 MCP 相关内容。如果直接把所有工具塞给 LLM，工具数量一多会难以管理，也缺少权限边界。

### 处理

新增 SkillRegistry：

```text
config/skills/*.json
```

Skill 声明：

```text
skill_id
workflow_id
default_inputs
allowed_tool_scopes
mcp_servers
tags
enabled
```

### 面试可讲点

Skill 更像 FastAPI 的 APIRouter：它不是一个函数，而是一组能力、默认 workflow、依赖和权限声明。这样比“工具列表”更适合工程化扩展。

## 89. MCP 先做 Catalog，不直接执行外部 MCP Server

### 现象

MCP 可以连接外部工具和资源，但如果第一版就允许启动 stdio/http/sse 外部 server，会引入命令执行、网络访问和权限问题。

### 处理

新增 MCPRegistry：

```text
config/mcp_servers/*.json
```

当前只保存：

```text
server_id
transport
enabled
allowed_tool_scopes
tools
input_schema
metadata
```

真实执行仍不开放，后续需要在 ToolExecutor 权限模型后面接入。

### 面试可讲点

MCP 的关键不是“能连上外部工具”，而是有清晰的工具目录、权限、schema 和审计边界。先做 catalog 是更安全的工程切分。

## 90. Skill 引用 MCP Server 需要校验

### 现象

Skill 配置里可以写：

```text
mcp_servers: ["local_agent_tools"]
```

如果引用了不存在的 MCP server，后续运行时才失败会很难排查。

### 处理

新增：

```text
validate_skill_links()
```

在 reload 时检查 skill 引用的 MCP server 是否存在。

### 验证

```text
GET /skills -> rag_research
GET /mcp/servers -> local_agent_tools
validate_skill_links() -> []
```

### 面试可讲点

配置化系统要尽早校验引用关系。Skill 和 MCP server 是跨文件配置，reload 阶段就应该发现断链。

## 91. Skill/MCP reload 属于管理操作，必须鉴权

### 现象

`POST /skills/reload` 和 `POST /mcp/reload` 会重新加载能力配置，属于管理操作。

### 处理

复用 API Key 鉴权。

验证：

```text
without key -> 401
with key    -> 200
GET list    -> 200
```

### 面试可讲点

动态 reload 改变 Agent 能力边界，必须按管理接口处理，不能和普通只读列表接口一样公开。

## 92. 项目内 Skill 本体与 Registry 配置需要分层

### 现象

`resume-writer` 原本已经是一个 Codex-style skill 文件夹，包含：

```text
SKILL.md
references/project_highlights.md
references/resume_principles.md
```

但它放在项目根目录，后端 `SkillRegistry` 只能读取 `config/skills/*.json`，无法明确知道这个 skill 本体的位置。

### 处理

新增项目内统一目录：

```text
skills/resume-writer
```

并新增 registry 配置：

```text
config/skills/resume_writer.json
```

配置中补充：

```text
skill_path
instructions_path
```

这样后端可以通过 `/skills` 发现这个能力，同时 Codex-style skill 仍保持 `SKILL.md + references` 的标准结构。

### 面试可讲点

Skill 的“能力声明”和“执行说明”应分层：JSON 配置适合机器加载和权限控制，`SKILL.md` 适合承载 Agent 的操作流程与领域知识。这类似 FastAPI 中 router 注册与具体业务逻辑文件的分离。

## 93. Skill 路径需要在 reload 阶段做断链校验

### 现象

如果 `config/skills/*.json` 中写了不存在的 `skill_path` 或 `instructions_path`，系统启动时可能不报错，但真正使用 skill 时才失败。

### 处理

扩展 `validate_skill_links()`，在 reload 时校验：

```text
skill_path exists
instructions_path is file
MCP server reference exists
```

### 面试可讲点

配置化系统要尽量 fail fast。Skill 是跨文件配置，如果不在 reload 阶段做断链校验，线上问题会变成“运行到某个 Agent 节点才失败”，排查成本更高。

## 94. Windows 下中文 Skill 校验脚本默认编码失败

### 现象

运行 Codex skill 校验脚本时出现：

```text
UnicodeDecodeError: 'gbk' codec can't decode byte ...
```

原因是 Windows Python 在未开启 UTF-8 模式时，`Path.read_text()` 默认使用系统编码 GBK，而 `skills/resume-writer/SKILL.md` 是 UTF-8 中文文件。

### 处理

验证时显式开启 UTF-8 模式：

```powershell
$env:PYTHONUTF8='1'
python C:\Users\junjie jiang\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\skills\resume-writer
```

验证结果：

```text
Skill is valid!
```

### 面试可讲点

跨平台工程里，中文配置、Markdown 文档和脚本校验要明确编码策略。Windows 默认编码和 Linux/macOS 默认 UTF-8 不一致，CI 或本地工具最好统一设置 UTF-8，避免“文件没问题但工具读取失败”的假性错误。

## 95. 评测集过小会导致消融结论不稳定

### 现象

原始评测集只有 4 条样本，且集中在少数 RFC 问题上。早期报告里 BM25 表现非常强，Hybrid/Rerank 没有明显优势，容易得出“向量和 rerank 没用”的错误结论。

### 处理

将 `app/eval/dataset.jsonl` 扩充到 16 条，覆盖：

```text
TLS 1.3: 0-RTT、PSK forward secrecy、KeyUpdate、cipher suite
QUIC: transport、connection migration、streams、path validation、idle timeout、immediate close
HTTP semantics: 404、cacheable responses、GET、PUT、Content-Type、validators
```

每条样本保留：

```text
question
gold_chunk_ids
answer_keywords
```

这样同一份数据既能评测检索，也能评测 Agent 最终回答。

### 面试可讲点

RAG 评测集不能只测几个“关键词强匹配”的问题，否则 BM25 会被高估。扩充样本时要覆盖不同文档、不同任务类型和不同表达方式，才能看出 Hybrid Search 与 Rerank 的真实价值。

## 96. Agent 评测不能只看检索命中

### 现象

原评测只调用 `knowledge_search`，只能说明检索工具是否召回 gold chunk，无法回答：

```text
workflow 是否跑通
节点是否成功
工具调用是否成功
最终答案是否覆盖关键事实
引用是否命中证据
```

### 处理

新增 Agent/Workflow 级评测：

```text
AgentRunSuccessRate
AgentCitationHit@5
AnswerKeywordCoverage
AgentNodeSuccessRate
AgentToolSuccessRate
AgentAvgLatencyMs
```

评测入口复用 `workflow_service.run()`，以 deterministic workflow agent 跑完整链路。

### 面试可讲点

Agent 评测要比 RAG 检索评测多一层。检索命中只是 evidence 层，Agent 还要评估 plan、tool call、critic、answer、citation 的完整执行质量。

## 97. Gold chunk 需要覆盖相邻有效证据，避免假性未命中

### 现象

扩充评测后，QUIC path validation 和 idle timeout 两个样本出现“未命中”，但 retrieved chunks 是同一小节的相邻证据，内容语义上可以回答问题。

### 处理

对这类跨相邻 chunk 的问题扩展 `gold_chunk_ids`：

```text
path validation: c0344/c0348/c0349/c0354
idle timeout: c0389/c0392/c0393
```

重新运行后，Hybrid + Rerank 的 Recall@5 达到 100%，AgentCitationHit@5 也达到 100%。

### 面试可讲点

RAG 评测的 gold label 不是只能有一个 chunk。父子 chunk、滑窗 chunk 和相邻 chunk 会让“正确证据”天然分布在多个 chunk 中，评测集需要允许多 gold，否则会误伤真实可用的检索结果。

## 98. 临时评测脚本没有关闭检索客户端会出现 unclosed session 警告

### 现象

直接用临时 Python 片段调用 `run_eval()` 时出现：

```text
Unclosed client session
Unclosed connector
```

原因是临时片段没有执行 `await retriever.close()`。

### 处理

正式报告脚本 `scripts/run_eval_report.py` 在 `finally` 中关闭 retriever：

```text
await retriever.close()
```

后续评测统一使用：

```powershell
python scripts/run_eval_report.py
```

### 面试可讲点

异步客户端生命周期要统一管理。临时脚本和正式服务都要确保 ES/http client 被关闭，否则容易在评测、CI 或长时间运行时留下连接资源问题。

## 99. 大规模评测集需要可复现生成，但要警惕自动标注噪声

### 现象

手工维护 16 条样本适合快速回归，但无法充分覆盖 RFC 文档中的不同章节。直接人工扩到几十上百条成本较高。

### 处理

新增脚本：

```text
scripts/generate_large_eval_dataset.py
```

从 `data/parsed/rfc_parent_child_chunks.jsonl` 中按文档均衡抽样，生成：

```text
app/eval/dataset_large.jsonl
```

当前命令：

```powershell
python scripts/generate_large_eval_dataset.py --max-cases 60
```

生成结果：

```text
60 cases
TLS 1.3: 20
QUIC: 20
HTTP semantics: 20
```

### 重要处理

大集使用 section + chunk keywords 生成问题，并把目标 chunk 的相邻 sibling chunk 一起加入 `gold_chunk_ids`，避免 chunk 边界导致假性未命中。

### 面试可讲点

大规模自动评测集适合做压力测试、回归测试和消融趋势观察；小规模人工集适合做高质量结论。两者要结合使用，不能只看自动生成集的绝对分数。

## 100. 自动生成评测问题会引入机械文本和切词噪声

### 现象

大集报告中出现了一些机械问题，例如：

```text
What does TLS 1.3 say about Introduction and Introduction and primary?
```

也出现了 chunk 边界切词导致的关键词噪声。

### 处理

在生成器中增加 stopwords 过滤、关键词长度过滤和文档均衡抽样。当前仍保留大集作为“可复现压力评测”，并将 16 条人工集作为主要展示集。

### 面试可讲点

自动评测集不是越大越好。规模提升后要同时关注 label quality、问题自然度和 gold evidence 质量。工程上可以先用规则生成扩大覆盖，再抽样人工审核形成高质量 benchmark。

## 101. 60 条大规模评测结果

### 结果

运行命令：

```powershell
python scripts/run_eval_report.py --dataset app/eval/dataset_large.jsonl --output reports/eval_report_large.md
```

结果：

```text
Dataset size: 60
Elapsed: 292882.32 ms

bm25_only:
Recall@5 = 90.00%
MRR@10 = 67.32%
Citation Accuracy = 51.67%

hybrid_rerank_metadata:
Recall@5 = 91.67%
MRR@10 = 75.69%
Citation Accuracy = 65.00%

AgentRunSuccessRate = 100.00%
AgentCitationHit@5 = 91.67%
AnswerKeywordCoverage = 86.67%
AgentNodeSuccessRate = 100.00%
AgentToolSuccessRate = 100.00%
AgentAvgLatencyMs = 1465.10 ms
```

相对 `bm25_only`：

```text
Recall@5: +1.67 pp / +1.85%
MRR@10: +8.38 pp / +12.44%
Citation Accuracy: +13.33 pp / +25.81%
```

### 面试可讲点

在更大且更偏 section-based 的评测集上，BM25 仍然很强，但 Hybrid + Rerank + Metadata 在排序质量和首条引用准确率上有明显提升。这个结论比 4 条小样本更可信，也更能解释为什么不是只做向量检索。

## 102. 真实 MCP 执行要接在 Registry 与 Scope 后面

### 现象

此前 MCP 只做了 catalog：

```text
config/mcp_servers/*.json
GET /mcp/servers
```

这能展示工具目录，但不能真正调用外部 MCP server。

### 处理

新增：

```text
app/services/mcp_client.py
POST /mcp/servers/{server_id}/tools/{tool_name}/call
```

支持：

```text
internal -> 调用本项目 ToolRegistry
stdio   -> 启动外部 MCP stdio server，执行 initialize + tools/call
http    -> 发送 JSON-RPC tools/call
sse     -> 显式返回未实现
```

同时 Agent ToolExecutor 支持：

```text
mcp:<server_id>:<tool_name>
```

### 面试可讲点

没有把 MCP 执行直接写进业务节点，而是放在 registry、scope、schema validation 后面。这样外部工具和内部工具共享同一套权限边界和 trace/tool_call 记录。

## 103. 外部 MCP 默认不开放 external scope

### 现象

外部 MCP tool 一般属于 `external` scope。如果默认开放，会让 Agent 获得网络、文件或进程类能力，风险过高。

### 处理

默认 `ALLOWED_TOOL_SCOPES` 仍为：

```text
retrieval,memory,planning
```

需要真实调用外部 MCP 时，显式开启：

```powershell
$env:ALLOWED_TOOL_SCOPES="retrieval,memory,planning,external"
```

同时 MCP server 自身也有 `allowed_tool_scopes`，工具 scope 必须同时通过全局和 server 两层校验。

### 面试可讲点

外部 MCP 执行等价于扩大 Agent 能力边界，必须 opt-in。全局 scope 控制“系统允许什么”，server scope 控制“这个 MCP server 自己允许什么”。

## 104. HTTP MCP Client 要禁用系统代理环境

### 现象

本地 HTTP MCP 冒烟测试时，访问 `127.0.0.1` mock server 出现：

```text
HTTPStatusError: 502 Bad Gateway
```

原因是 `httpx` 默认读取系统代理环境，可能把本地 MCP 请求转发到代理，导致本地/内网工具调用异常。

### 处理

在 MCP HTTP client 中设置：

```text
trust_env=False
```

验证后本地 HTTP JSON-RPC MCP 调用成功：

```text
transport=http
result=http:hello
```

### 面试可讲点

Agent 工具调用经常访问本地或内网服务，HTTP client 不能盲目继承系统代理。否则工具链路会出现“代码没错但请求被代理劫持”的隐蔽问题。

## 105. Stdio MCP 要按 Content-Length 帧协议读写

### 现象

MCP stdio 不是普通的一行 JSON，而是类似 LSP 的 framed JSON-RPC：

```text
Content-Length: <bytes>

{jsonrpc payload}
```

如果直接 `readline()` 读 JSON，会卡住或读不完整。

### 处理

实现 `_write_stdio_message()` 和 `_read_stdio_message()`：

```text
写入 Content-Length header + UTF-8 JSON body
读取 header，解析 Content-Length，再 readexactly body
```

本地 mock stdio server 验证：

```text
transport=stdio
result=echo:hello-mcp
```

### 面试可讲点

MCP stdio 的关键不是“能启动进程”，而是正确实现 JSON-RPC framing、初始化握手、超时和进程回收。否则很容易出现死锁、半包读取或进程泄漏。

## 106. 容器镜像必须复制 Skill 本体，否则 registry 会断链

### 现象

Dockerfile 初版只复制了：

```text
app
config
scripts
```

但 `config/skills/resume_writer.json` 里引用：

```text
skills/resume-writer/SKILL.md
```

如果容器镜像不复制 `skills/`，本地 preflight 能过，容器内 reload 或校验会失败。

### 处理

Dockerfile 增加：

```text
COPY skills skills
```

同时新增 `scripts/preflight.py` 校验 `skill_path` 和 `instructions_path`，避免打包后才发现资源缺失。

### 面试可讲点

生产化不是只写 Dockerfile，还要保证配置引用的非代码资源也进入镜像。Skill、prompt、workflow config 都属于运行时资产，缺一类都会导致本地和容器行为不一致。

## 107. 健康检查要区分 live 和 ready

### 现象

原来只有：

```text
GET /health
```

它同时检查 API、ES、Redis、PostgreSQL。这样不适合作为容器探针：依赖短暂不可用时，如果 liveness 失败，容器可能被错误重启。

### 处理

新增：

```text
GET /health/live
GET /health/ready
```

- live: 只证明进程活着。
- ready: 检查 ES/Redis/PostgreSQL，不可用时返回 503。

验证：

```text
GET /health/live -> 200
GET /health/ready -> 200
```

### 面试可讲点

Liveness 和 readiness 语义不同。Liveness 失败意味着进程需要重启；readiness 失败只表示暂时不该接流量。RAG 系统依赖 ES/Redis/PostgreSQL，更应该分层探测。

## 108. 请求日志需要 request_id 和耗时

### 现象

此前只依赖默认日志，无法快速关联一次请求、trace、workflow_run 和外部工具调用。

### 处理

新增 `RequestLoggingMiddleware`：

```text
X-Request-ID
X-Process-Time-Ms
method
path
status
latency_ms
```

验证 smoke 测试时日志能看到每个接口的 request_id 和耗时。

### 面试可讲点

生产环境排查 Agent 问题时，request_id 是入口链路，trace_id 是 Agent 内部链路。两者结合才能从 HTTP 请求一路追到工具调用、检索事件和最终回答。

## 109. Docker Compose 需要服务健康条件，而不是只 depends_on

### 现象

普通 `depends_on` 只保证容器启动顺序，不保证 ES/Redis/PostgreSQL 已经可用。API 太早启动时，ready 检查和首次请求可能失败。

### 处理

为基础设施增加 healthcheck，并让 API 使用：

```text
depends_on:
  condition: service_healthy
```

验证：

```text
docker compose config --quiet
```

通过。

### 面试可讲点

容器编排里“启动了”和“可用了”不是一回事。尤其 ES 启动较慢，生产化 compose 至少要加 healthcheck，避免 API 抢跑。

## 110. 生产化需要 preflight 和 smoke 两类检查

### 现象

仅靠单元编译不能发现配置断链、依赖不可用、API 路由挂载缺失等问题。

### 处理

新增：

```text
scripts/preflight.py
scripts/smoke_api.py
```

验证：

```text
python -m compileall app scripts
python scripts/preflight.py --strict-deps
python scripts/smoke_api.py --strict-ready
```

结果均通过。

### 面试可讲点

preflight 关注“配置和依赖是否具备运行条件”，smoke 关注“API 的关键入口是否可访问”。这两类检查比只跑单测更贴近部署前验收。

## 111. Skill 从 Catalog 升级为产品执行入口

### 现象

此前 `/skills` 只能列出 Skill 配置，不能直接执行：

```text
GET /skills
GET /skills/{skill_id}
```

这意味着 Skill 还只是“可发现能力”，不是产品 API。

### 处理

新增：

```text
POST /skills/{skill_id}/run
POST /skills/{skill_id}/stream
```

执行时：

```text
读取 SkillDefinition
校验 enabled
校验 workflow_id 存在
合并 default_inputs 和 request.inputs
只允许覆盖 top_k/use_llm_* 等 workflow-safe 字段
调用 workflow_service.run/stream
```

### 面试可讲点

Skill 类似 FastAPI Router：它不只是工具说明，而是一个产品化能力入口。用户调用 Skill，不需要知道底层 workflow DAG，只需要传入问题和少量 inputs。

## 112. Skill 执行入口必须鉴权

### 现象

`/skills/{skill_id}/run` 会触发完整 workflow，包括检索、工具调用、记忆写入和 trace 落库。它不是只读 catalog。

### 处理

为以下接口增加 API Key 鉴权：

```text
POST /skills/{skill_id}/run
POST /skills/{skill_id}/stream
```

验证：

```text
without API key -> 401
with API key    -> 200
```

### 面试可讲点

产品化 API 要区分“发现能力”和“执行能力”。列表接口可以公开，执行接口会消耗资源并改变系统状态，必须鉴权。

## 113. Skill inputs 不能无边界覆盖 workflow request

### 现象

如果允许用户通过 `inputs` 任意覆盖 workflow 字段，可能改变 `workflow_id`、`session_id` 或注入不符合预期的执行参数。

### 处理

`request.inputs` 只允许覆盖：

```text
top_k
use_llm_planner
use_llm_critic
use_llm_answer
```

`question/session_id/workflow_id` 分别来自显式请求字段和 Skill 配置。

### 面试可讲点

配置化入口不能变成任意参数注入入口。Skill 的 default_inputs 是默认策略，请求 inputs 只能覆盖安全白名单内的运行参数。

## 114. TestClient 跨事件循环关闭 async Redis 会失败

### 现象

在 smoke 脚本中手动调用：

```text
asyncio.run(close_app_resources())
```

出现：

```text
RuntimeError: Event loop is closed
```

原因是 FastAPI TestClient 自己管理 lifespan 和事件循环，Redis async connection 绑定在 TestClient 的 loop 上，外部再开一个 loop 关闭会失败。

### 处理

改为：

```python
with TestClient(app) as client:
    ...
```

让 TestClient context 自动触发 lifespan shutdown。

### 面试可讲点

异步资源生命周期要和创建它的事件循环一致。测试脚本里不要跨 loop 关闭 async client，否则会出现本地偶发但 CI 常见的 loop closed 问题。

## 115. 前端控制台不要引入过重构建链

### 现象

项目核心竞争力在 RAG、Agent、Workflow、Trace、Skill/MCP 和生产化工程。如果为了演示前端再引入 React/Vite/Node 构建链，会增加部署变量，也会让面试讲解的重点被前端工程复杂度稀释。

### 处理

采用 FastAPI 原生托管静态控制台：

```text
GET /      -> 307 redirect to /app/
GET /app/ -> 前端控制台
GET /app/app.js
GET /app/styles.css
```

前端实现为 `app/static/index.html`、`app/static/styles.css`、`app/static/app.js`，直接调用同源 API，不需要额外前端服务。

### 面试可讲点

这是一个偏后端和 Agent 基础设施的项目，前端的目标是“可演示、可排障、可运营”，不是追求复杂 UI 技术栈。静态控制台能降低部署成本，同时给评测、trace、workflow、skill 执行提供统一入口。

## 116. 前端资产必须纳入 smoke test

### 现象

只检查 `/health` 和后端 API 可能出现一种问题：服务看起来健康，但演示入口 `/app/` 或 JS/CSS 静态资源缺失，最后在面试现场才发现页面打不开。

### 处理

把前端入口加入 `scripts/smoke_api.py`：

```text
GET /app/     -> 200
GET /app/app.js -> 200
```

另外用 TestClient 单独验证：

```text
/              307 /app/
/app/          200 text/html
/app/styles.css 200 text/css
/app/app.js   200 text/javascript
```

### 面试可讲点

生产化检查不应该只覆盖业务 API，也要覆盖用户实际访问路径。对这个项目来说，前端控制台是产品化展示入口，因此必须进入 smoke test。

## 117. 浏览器插件访问本地页面被拦截时要有替代验证

### 现象

尝试用 Codex in-app Browser 打开：

```text
http://127.0.0.1:8000/app/
http://localhost:8000/app/
```

返回：

```text
net::ERR_BLOCKED_BY_CLIENT
```

这不是后端路由失败，因为 TestClient 和 smoke test 均能返回 200。

### 处理

采用两层替代验证：

```text
python -m compileall app scripts
python scripts/smoke_api.py --strict-ready
FastAPI TestClient 检查 /、/app/、/app/styles.css、/app/app.js
```

### 面试可讲点

排障时要先区分“应用错误”和“验证工具环境错误”。本例中浏览器插件被客户端策略拦截，但后端静态资源实际可访问，因此用 TestClient 和 smoke test 作为确定性验证路径。

## 118. Demo 控制台 API Key 存储的安全边界

### 现象

前端控制台需要调用 Skill、Workflow、Trace、Eval 等接口。为了便于本地演示，页面把 API Key 保存到 `localStorage` 并通过 `X-API-Key` 请求头发送。

### 处理

将其定位为本地演示和内部运维控制台方案：

```text
localStorage -> 方便本地反复测试
X-API-Key    -> 复用后端已有鉴权
```

生产环境应进一步升级为更严格的会话鉴权、短期 token、权限分级和审计日志。

### 面试可讲点

安全设计要讲清楚边界。`localStorage + API Key` 适合本地 MVP 和内部演示，但不应该包装成最终生产登录方案；生产版本应接入用户体系、RBAC、token 过期和操作审计。

## 119. 评测集可视化不能直接让前端读本地文件

### 现象

评测集位于：

```text
app/eval/dataset.jsonl
app/eval/dataset_large.jsonl
```

前端运行在浏览器里，不能直接读取服务端本地文件。如果把 JSONL 文件路径暴露给浏览器，一方面访问不到，另一方面也会形成不必要的文件路径泄露。

### 处理

新增只读汇总接口：

```text
GET /eval/dataset?name=default&sample_size=12
GET /eval/dataset?name=large&sample_size=12
```

后端只允许 `default` 和 `large` 两个白名单数据集名，然后返回：

```text
dataset_size
source_doc_counts
task_type_counts
gold_count_distribution
keyword_count_distribution
sample_cases
ablation_dimensions
```

### 面试可讲点

这是一个典型的产品化边界：浏览器不直接碰服务端文件系统，而是通过受控 API 获取可展示的数据摘要。这样既安全，也便于以后把评测集迁移到数据库或对象存储。

## 120. 评测运行要区分数据集选择和是否跑 Agent

### 现象

原先 `/eval/run` 默认只跑 `app/eval/dataset.jsonl`，前端无法选择更大的 `dataset_large.jsonl`，也无法跳过耗时更高的 Agent workflow 评测。

### 处理

扩展 `EvalRunRequest`：

```text
dataset_name: default | large
include_agent_eval: true | false
```

前端 Eval 面板提供：

```text
Dataset: Default / Large
Agent Eval: Include / Skip
```

### 面试可讲点

评测系统要把“数据集规模”和“评测范围”显式参数化。检索消融可以高频运行，完整 Agent 评测更接近端到端验收但耗时更高，两者应该由同一套接口清晰区分。

## 121. 首次评测存在 embedding/rerank 模型冷启动成本

### 现象

执行默认 16 条评测集、跳过 Agent Eval 的轻量评测时，接口成功返回 200，但首次耗时约 70 秒。日志中可以看到：

```text
Load pretrained SentenceTransformer: sentence-transformers/all-MiniLM-L6-v2
cross-encoder/ms-marco-MiniLM-L6-v2
```

原因是首次运行需要加载 embedding 模型和 cross-encoder rerank 模型，并访问 HuggingFace metadata。后续模型进入本地缓存和进程内缓存后会明显变快。

### 处理

本轮没有为了隐藏耗时而删除 rerank，而是：

```text
1. 保留真实模型评测，确保指标可信
2. 前端允许跳过 Agent Eval，降低一次评测的额外 workflow 成本
3. 在文档中记录模型冷启动，面试时可解释生产预热策略
```

### 面试可讲点

真实 RAG 系统的评测耗时不只来自 ES 查询，也来自模型加载、tokenizer、reranker 和网络 metadata 检查。生产环境可以通过容器启动预热、模型本地化、HF_TOKEN、离线缓存和常驻 worker 降低冷启动。

## 122. 本地端口占用时不要强行复用 8000

### 现象

启动前检查端口发现：

```text
8000 Listen
```

说明本机已有服务占用 8000。如果直接再起一个 uvicorn，会启动失败或误以为访问的是新代码。

### 处理

本轮新启动服务在：

```text
http://127.0.0.1:8001/app/
```

并用 HTTP 请求和浏览器确认页面返回 200。

### 面试可讲点

本地演示时要先确认端口归属，避免“我改了代码但页面没变”的假象。换端口启动新实例，是一种比杀进程更稳妥的演示排障方式。

## 123. PowerShell 调用带查询参数 URL 时要给 URL 加引号

### 现象

在 PowerShell 中直接执行：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8001/eval/dataset?name=large&sample_size=3
```

报错：

```text
The ampersand (&) character is not allowed.
```

原因是 `&` 在 PowerShell 中是操作符，不加引号时不会被当作 URL 查询参数的一部分。

### 处理

改为：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8001/eval/dataset?name=large&sample_size=3'
```

验证结果：

```text
name=large
dataset_size=60
rfc8446-tls13=20
rfc9000-quic=20
rfc9110-http-semantics=20
```

### 面试可讲点

很多本地验证失败并不是后端接口失败，而是 shell 对特殊字符的解析导致请求根本没有按预期发出。排障时要区分“命令行语法问题”和“服务端业务问题”。

## 124. 评测指标只展示 JSON 不利于面试表达

### 现象

`/eval/run` 返回的是结构化 JSON，包含多组消融配置：

```text
bm25_only
vector_only
hybrid_no_rerank
hybrid_rerank
hybrid_rerank_metadata
```

以及多个指标：

```text
Recall@5
MRR@10
CitationAccuracy
ToolSuccessRate
AgentRunSuccessRate
AgentCitationHit@5
AnswerKeywordCoverage
AgentAvgLatencyMs
```

如果前端只输出 JSON，面试官很难快速看出哪种方案更好。

### 处理

前端新增图表渲染：

```text
检索消融指标对比:
Recall@5 / MRR@10 / CitationAccuracy / ToolSuccessRate

Agent 端到端评测指标:
AgentRunSuccessRate / AgentCitationHit@5 / AnswerKeywordCoverage / AgentAvgLatencyMs
```

图表仍然使用原生 HTML/CSS/JS 实现，不引入额外前端依赖。

### 面试可讲点

评测系统不只是“能跑指标”，还要能帮助人做判断。把消融结果图表化后，可以清楚讲出 BM25、向量、Hybrid、Rerank、Metadata Enhancement 每一步带来的收益。

## 125. 前端中文化时保留必要工程术语

### 现象

早期控制台大量使用英文按钮和标题，例如：

```text
Overview
Workflow
Evaluation
Load Dataset
Run Eval
```

对中文面试演示不够友好。

### 处理

将主要 UI 文案改为中文：

```text
总览
技能
工作流
评测
加载数据集
运行评测
```

同时保留 `Trace`、`API Key`、`Recall@5`、`MRR@10` 等行业常用术语。

### 面试可讲点

产品化不是单纯加页面，还包括让目标受众更容易理解。中文化降低演示成本，保留关键英文指标则方便和工程指标、论文指标、简历表述保持一致。

## 126. 浏览器自动化中旧 tab 句柄可能失效

### 现象

验证前端时，浏览器工具返回：

```text
Tab 1 is not part of browser session
```

说明之前保存的 tab 句柄已经不属于当前浏览器会话。

### 处理

重新读取浏览器 tab 列表并绑定当前 tab：

```text
browser.tabs.list()
browser.tabs.get(tab_id)
```

之后再打开 `http://127.0.0.1:8001/app/` 验证。

### 面试可讲点

自动化验证也有状态管理问题。遇到这类错误时，不应该先怀疑业务页面，而是先恢复测试工具的会话状态，再继续验证。

## 127. 业务 Skill 不能只停留在设计文档

### 现象

无人机任务规划如果只写成架构方案，面试时容易被追问：

```text
具体 tool 怎么接？
workflow 能不能跑？
trace 里有没有 tool_calls？
业务安全边界在哪里？
```

### 处理

实现 deterministic MVP：

```text
Skill: drone_mission_planner
Workflow: drone_mission_planning_v1
Tools:
  drone_mission_parse
  drone_map_query
  drone_no_fly_zone
  drone_weather
  drone_route_plan
  drone_risk_assessment
  drone_mission_export
```

示例输入：

```text
明天上午 9 点让两架无人机巡检 A 区域的输电线路，重点检查杆塔和疑似异物。
```

输出可人工审批的无人机任务规划方案，不下发飞控命令。

### 面试可讲点

这说明项目不是只会做 RAG QA，而是能把业务拆成 Skill / Workflow / Tool。LLM 或自然语言入口负责表达需求，确定性工具负责地图、禁飞区、天气、航线和风险，最终输出可审计、可审批的业务计划。

## 128. 高风险业务必须把“规划”和“执行”分开

### 现象

无人机属于高风险物理世界任务。如果 Agent 直接根据自然语言下发飞控命令，会有明显安全问题：

```text
误解任务目标
穿越禁飞区
天气条件不满足
电量不足
绕过人工审批
```

### 处理

当前 `drone_mission_export` 只输出：

```text
review_only_json
Markdown 审批说明
```

并在最终答案中明确：

```text
当前结果仅用于任务规划和人工审批，不会直接下发飞控命令。
```

### 面试可讲点

Agent 业务化时，最重要的是能力边界。规划可以自动化，执行必须权限化、审批化和审计化。这个项目把高风险动作留给未来单独的 `mission_dispatch` tool，并要求 RBAC、人工确认和 trace 审计。

## 129. 新业务工具需要扩展 tool scope

### 现象

原系统默认允许：

```text
retrieval,memory,planning
```

无人机工具注册为：

```text
scope=mission
```

如果不扩展 `ALLOWED_TOOL_SCOPES`，ToolExecutor 会拒绝执行。

### 处理

将默认配置和 `.env.example` 扩展为：

```text
ALLOWED_TOOL_SCOPES=retrieval,memory,planning,mission
```

并在 `config/skills/drone_mission_planner.json` 中声明：

```text
allowed_tool_scopes: ["mission"]
```

### 面试可讲点

工具注册不仅要有函数，还要有权限模型。scope 能把 retrieval、memory、planning、mission 等能力隔离，后续接真实飞控时可以把 dispatch 放在更高风险 scope 中单独审批。

## 130. PowerShell 中文 here-string 会导致业务解析失真

### 现象

用 PowerShell here-string 执行临时 Python 测试时，中文问题被传成：

```text
???? 9 ????????? A ????????????????????
```

导致任务解析结果退化为：

```text
mission_type=general_survey
drone_count=1
targets=visual_inspection
```

### 处理

验证时改用 Unicode escape 构造中文字符串：

```python
question = "\u660e\u5929\u4e0a\u5348 ..."
```

重跑后正确得到：

```text
mission_type=powerline_inspection
drone_count=2
targets=tower, foreign_object
time_window=明天上午
```

### 面试可讲点

本地测试中的编码问题会直接影响自然语言解析结果。排障时要区分业务 parser 问题和测试输入已经损坏的问题；对中文项目尤其要注意终端编码和请求编码。

## 131. 新增业务 Skill 后要重启长驻 uvicorn 进程

### 现象

8001 端口上的 uvicorn 是之前启动的长驻进程，启动参数没有 `--reload`。新增 tool、workflow 和 skill 配置后，如果不重启，前端和接口仍然可能读到旧代码或旧 registry 缓存。

### 处理

先停止 8001 的旧监听进程，再重新启动：

```powershell
Stop-Process -Id <old_pid> -Force
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

重启后 `/skills` 能看到：

```text
drone_mission_planner
```

### 面试可讲点

本地演示环境也需要生命周期意识。配置型能力上线后，要确认服务进程是否 reload；否则容易出现“文件已修改但接口没变化”的假象。

## 132. 业务 Skill 应进入 smoke test

### 现象

无人机任务规划虽然可以单独调用成功，但如果不进入 smoke test，后续修改 workflow runtime、tool scope 或 skill registry 时可能悄悄破坏这个业务入口。

### 处理

在 `scripts/smoke_api.py` 中新增：

```text
POST /skills/drone_mission_planner/run -> 200
```

并校验：

```text
workflow_id == drone_mission_planning_v1
answer contains powerline_inspection
answer contains parallel_area_split
tool_calls contains drone_mission_export
```

### 面试可讲点

业务能力不是“能跑一次”就结束，而是要进入回归验证。这样项目从技术 demo 进一步接近生产化能力平台。

## 133. GitHub 展示版 README 不能包含简历描述

### 现象

准备发布 GitHub 时，README 需要展示项目能力，而不是呈现求职简历内容。早期 README 中还出现了与简历相关的描述和示例入口，不适合作为公开项目主页的核心叙事。

### 处理

重写 README，保留：

```text
项目架构图
核心能力
技术亮点
目录结构
快速启动
数据处理与入库
Skill 运行
评测
生产化检查
安全设计
文档索引
```

去掉简历式项目经历描述，只保留工程项目说明。

### 面试可讲点

GitHub README 和简历不是同一种材料。README 面向工程读者，要讲清楚怎么运行、架构如何设计、核心模块在哪里、如何验证；简历面向招聘，要强调角色、动作和结果。

## 134. 发布公开仓库前要排除个人文件和生成日志

### 现象

项目目录中存在：

```text
resume.pdf
reports/frontend_server_8001.log
reports/frontend_server_8001.err.log
data/raw/*.txt
data/parsed/*.jsonl
```

其中 `resume.pdf` 是个人文件，运行日志不适合提交，原始/解析后的大文件会增加仓库体积。

### 处理

扩展 `.gitignore`：

```text
resume.pdf
reports/*.log
reports/*.err.log
data/raw/*
data/parsed/*
```

保留：

```text
data/raw/.gitkeep
data/parsed/.gitkeep
```

### 面试可讲点

发布工程项目时要有仓库卫生意识：个人文件、密钥、运行日志、大型生成物都不应该直接进入 GitHub。数据处理脚本和复现实验方法比提交大文件更重要。

## 135. GitHub 推送需要本地仓库和认证两步

### 现象

执行发布前检查时发现：

```text
fatal: not a git repository
gh auth status -> You are not logged into any GitHub hosts
```

说明当前目录还不是 git 仓库，且 GitHub CLI 未登录。

### 处理

已完成本地部分：

```text
git init
git branch -M main
git add -A
git commit -m "Initial RAG agent platform"
```

但远端发布仍需要用户完成：

```powershell
gh auth login
```

并确认 GitHub 仓库名。

### 面试可讲点

发布流程分为本地版本管理和远端仓库发布。自动化助手可以准备 README、忽略规则、提交记录和验证结果，但 GitHub 认证必须由用户授权完成。

## 136. GitHub CLI 已登录但 token 可能缺少创建仓库权限

### 现象

执行：

```powershell
gh repo create rag-agent-decision-system --public --source . --remote origin --push
```

返回：

```text
GraphQL: Resource not accessible by personal access token (createRepository)
```

说明 `gh auth status` 虽然已登录，但当前 token 没有创建仓库所需权限。

### 处理

本地仓库和提交已经准备好：

```text
branch: main
commit: 435e82a Initial RAG agent platform
```

后续有两种解决方式：

```powershell
gh auth refresh -h github.com -s repo
```

或在 GitHub 网页端手动创建空仓库，再添加 remote 并 push。

### 面试可讲点

CI/CD 和发布流程中，“已登录”和“具备对应权限”是两件事。遇到 GitHub GraphQL 权限错误时，要检查 token scope，而不是只检查是否登录。
## 137. rag_quic_stream 时延偏高与并行检索分支语义

### 现象

分析 Agent 评测报告时发现 `rag_quic_stream` 明显慢于 mission/tool 类任务。Trace 中出现：

```text
retrieval_original
retrieval_rewritten
merge_evidence
critic
retrieval_original
retrieval_rewritten
merge_evidence
critic
answer
```

### 排查

查看 `app/services/workflow/nodes.py` 后确认，`retrieval_original` 与 `retrieval_rewritten` 都调用同一个 `knowledge_search` 工具，区别只在 query 来源：

- `retrieval_original` 使用用户原始问题 `state.agent_state.question`
- `retrieval_rewritten` 使用 `state.agent_state.rewritten_query`
- 如果 Critic 生成了 `followup_queries`，下一轮两个分支都会优先使用第一个 follow-up query

当前 `app/services/query_rewrite.py` 还是确定性占位实现：

```python
return question.strip()
```

因此首轮 `retrieval_original` 和 `retrieval_rewritten` 实际上检索的是同一句 query，只是保留了未来接入 LLM query rewrite / domain rewrite 的工作流扩展点。

### 重要处理

这个设计在架构上是合理的：并行分支让系统可以同时覆盖“用户原话召回”和“改写后的规范化问题召回”，再通过 `merge_evidence` 去重、加权和排序。但在当前未接入真正 query rewrite 的阶段，它会带来额外检索成本，收益暂时不明显。

### 面试可讲点

可以说明系统采用了 Router-driven Workflow Graph，而不是所有任务都走完整 Multi-Agent。RAG 路径中设计了 original/rewrite 双路召回，目的是提升专业术语、同义表达和规范查询的召回率；同时通过 trace 暴露每一路耗时和证据贡献。当前 query rewrite 仍是占位实现，因此评测中它主要体现架构可扩展性，后续可接 LLM rewrite、领域词典 rewrite 或 HyDE 类查询扩展。

## 138. BM25、向量检索与 Workflow 并行分支的层次区别

### 现象

分析 `retrieval_original` / `retrieval_rewritten` 时，容易误以为它们分别对应 BM25 和向量检索。

### 排查

查看 `app/services/retriever.py` 后确认，这里有两层不同的“两路”：

第一层是 Workflow 层：

- `retrieval_original`：用原始 query 调用 `knowledge_search`
- `retrieval_rewritten`：用改写 query 调用 `knowledge_search`

第二层是 Retriever 层：

- `mode="bm25"`：只执行 ES `match` 查询
- `mode="vector"`：只执行 ES 原生 `knn` 查询
- `mode="hybrid"`：同一个 query 同时执行 BM25 和向量 kNN，再用加权 RRF 融合

当前 `knowledge_search` 默认参数是：

```python
retrieval_mode: Literal["bm25", "vector", "hybrid"] = "hybrid"
use_rerank: bool = True
```

因此一次 `knowledge_search` 在默认情况下内部会先做 hybrid 召回，再做 rerank。

### 重要处理

BM25 由 Elasticsearch `match` 查询实现，查询字段是 `text`，并过滤 `chunk_level=child`。向量检索由 ES `dense_vector` + 原生 `knn` 实现，查询向量由 `sentence-transformers/all-MiniLM-L6-v2` 生成，维度为 384，同样过滤 child chunk。

Hybrid 融合不是简单拼接，而是按 rank 做加权 RRF：

```text
BM25 权重:   0.45 / (60 + rank)
Vector 权重: 0.55 / (60 + rank)
```

相同 `chunk_id` 会合并得分，最后按融合分排序。

### 面试可讲点

可以强调检索链路是“两层召回 + 重排”：Workflow 层通过 original/rewrite query 扩大问题表达覆盖；Retriever 层通过 BM25/vector hybrid 同时兼顾关键词精确匹配和语义相似；最后 CrossEncoder rerank 和元数据调权提升最终证据质量。这个结构比单纯向量检索更适合规范、手册、任务规划这类既有术语精确性又有语义表达变化的场景。
## 139. GitHub 是否包含 Agent 体系评测改动的核对

### 现象

需要确认 GitHub 上是否已经更新 Agent 层评测能力，例如 `ToolSuccessRate`、`WorkflowCompletionRate`、`PlanCompleteness`、`ConstraintPassRate`、`TraceCoverage` 等指标。

### 排查

执行本地 Git 状态检查后发现：

```text
HEAD/main/origin/main: 6142d5b Add dependency caller observability
```

但 Agent 评测相关文件仍处于本地未提交状态：

```text
app/eval/agent_dataset.jsonl
tests/test_agent_eval_metrics.py
docs/agent_evaluation.md
reports/agent_eval_report.md
app/eval/metrics.py
scripts/run_eval_report.py
app/api/eval.py
app/schemas/eval.py
app/static/app.js
README.md
```

尝试执行 `git fetch origin` 实时确认远端状态时，GitHub 连接失败：

```text
Failed to connect to github.com port 443
```

### 结论

根据本地 Git 状态，Agent 体系评测还没有提交并推送到 GitHub。当前 GitHub 上最新可见提交仍应是依赖调用器可观测性相关提交，而不是 Agent 评测提交。

### 重要处理

后续需要先完成本地验证，再执行：

```powershell
git add ...
git commit -m "Add agent evaluation metrics"
git push origin main
```

由于本次 `fetch` 无法连接 GitHub，推送前需要再次确认网络和 GitHub token 状态。

### 面试可讲点

工程交付时要区分“本地已实现”和“远端已发布”。评测指标、报告和测试即使已经在本地完成，也必须通过 commit、push 和远端核对后，才能认为已经进入可展示版本。
## 140. Multi-Agent 在项目中的实际落点

### 现象

需要确认项目中的 Multi-Agent 不是只停留在文档设计，而是具体体现在哪些代码和运行链路中。

### 排查

核心落点包括：

- `config/workflows/supervisor_workflow_v1.json`：业务主入口 Workflow，定义 Supervisor、RAG、Tool、Mission Planning 等分支
- `app/services/workflow/definition.py`：WorkflowDefinition / WorkflowNodeSpec / WorkflowEdgeSpec，支持可配置节点和边
- `app/services/workflow/runtime.py`：WorkflowRuntime，负责节点调度、条件分支、并行分支、循环、trace 持久化
- `app/services/workflow/nodes.py`：具体 Agent 节点实现，包括 router、retriever、critic、answerer、mission parser、mission planner 等
- `app/services/agent/executor.py` 与 `app/tools/registry.py`：Agent 调用 Tool 的统一执行层

### 重要处理

项目中的 Multi-Agent 是 Router-driven Workflow Graph：

```text
supervisor_router
  -> direct_answer
  -> deterministic_tool
  -> retrieval_original + retrieval_rewritten -> merge_evidence -> critic -> answer
  -> mission_parse -> mission_context -> mission_route_plan -> mission_risk_review -> mission_export
```

其中每个 `node_type="agent"` 的节点可以看作一个 Agent 角色，每个节点都有结构化输入、输出、耗时、状态和 trace。

### 面试可讲点

不要把本项目讲成“多个 LLM 角色聊天”。更准确的说法是：系统采用 Supervisor 驱动的可配置 Multi-Agent Workflow Graph。不同 Agent 是工作流节点，不同 Tool 是节点内部能力。简单任务不会过度编排，复杂无人机任务才进入多阶段规划、上下文查询、航线生成、风险校验和审批导出链路。
## 141. 默认评测集高分是否合理的分析

### 现象

默认评测报告显示：

```text
hybrid_rerank Recall@5 = 100.00%
hybrid_rerank MRR@10  = 85.62% / 约 85.63%
ToolSuccessRate       = 100.00%
```

Agent 报告中也出现工具调用成功率 100%。

### 排查

默认 RAG 评测集 `app/eval/dataset.jsonl` 只有 16 条，问题集中在 RFC 8446、RFC 9000、RFC 9110 三份文档，且问题大多直接包含文档术语，例如 `QUIC streams`、`HTTP Content-Type`、`TLS KeyUpdate`。gold chunk 也来自同一批已入库 chunk。

更大规模的 `app/eval/dataset_large.jsonl` 有 60 条，指标下降为：

```text
hybrid_rerank_metadata Recall@5 = 91.67%
hybrid_rerank_metadata MRR@10  = 75.69%
```

说明默认集的 100% Recall 更像小样本、同源数据、术语匹配较强条件下的结果，而不是泛化能力上限。

Agent 评测集目前只有 4 条，且任务多为 deterministic workflow / deterministic tool。工具调用成功率 100% 表示工具没有异常返回或被权限拒绝，不代表每个业务结果都完全正确。RAG Agent 样例在 Docker/ES 不可用时仍可能因为 fallback 被记为工具调用成功，但 citation/constraint 指标会下降。

### 结论

默认评测结果作为开发阶段 smoke / regression 指标是合理的，可以说明 pipeline 跑通、hybrid + rerank 在小样本上有效。但作为面试或项目展示，需要主动说明局限：样本量小、同源、问题较直接、Agent case 数量不足、ToolSuccessRate 不等于任务质量。

### 面试可讲点

不要只说“Recall 100%”。更好的表述是：默认集用于验证检索链路正确性，所以高分符合预期；为了避免指标虚高，项目又扩展了 60 条 large eval，并单独设计 Agent 层指标，如 WorkflowCompletionRate、PlanCompleteness、ConstraintPassRate、TraceCoverage。这样能同时评估检索质量和任务规划链路可靠性。
## 142. 发布 Agent 评测与排障记录到 GitHub

### 现象

Agent 体系评测、报告和相关文档已经在本地完成，但尚未提交和推送到 GitHub。

### 处理规划

本次发布范围包括：

- Agent 评测集与指标实现
- Agent 评测报告生成脚本增强
- 前端评测指标展示标签
- README 与 Agent 评测说明文档
- 排障记录和面试可讲点

### 重要处理

发布前需要执行轻量验证：

```powershell
python -m compileall app scripts tests
pytest tests\test_dependency_caller.py tests\test_agent_eval_metrics.py -q
```

如果验证通过，再执行 `git add`、`git commit` 和 `git push origin main`。由于当前项目是面试展示项目，优先保证远端 README、报告和评测代码保持一致。

### 面试可讲点

项目展示不能只停留在本地实现，必须把可复现的评测代码、评测数据、报告和文档一起推送到远端仓库。这样面试官可以从 README 直接看到架构、指标和运行方式，也能从测试和报告判断实现不是口头设计。

## 143. GitHub push 因 443 端口不可达失败

### 现象

本地已经成功提交：

```text
cc99179 Add agent evaluation metrics
```

执行推送：

```powershell
git push origin main
```

失败：

```text
Failed to connect to github.com port 443 after 21074 ms
Could not connect to server
```

### 排查

继续执行网络连通性检查：

```powershell
Test-NetConnection github.com -Port 443
```

结果显示：

```text
PingSucceeded: True
TcpTestSucceeded: False
```

说明 DNS 和 ICMP 能到 GitHub，但 HTTPS/TCP 443 无法建立连接。该问题更像本机网络、代理、防火墙、VPN 或运营商链路问题，而不是 GitHub token、commit 或仓库权限问题。

### 重要处理

本地 Git 状态为：

```text
main...origin/main [ahead 1]
```

表示本地已经比 GitHub 多 1 个提交，只差网络恢复后再次执行 push。

### 面试可讲点

排查发布问题时要区分认证失败、权限失败和网络连通失败。这里 token 权限不是主要矛盾，因为错误发生在连接 GitHub 443 端口阶段；用 `Test-NetConnection` 可以快速确认是 TCP 连接不可达，而不是 Git 或代码问题。

## 144. GitHub 443 连通性恢复后的处理

### 现象

前一次 `git push origin main` 因 GitHub 443 端口不可达失败。随后重新检查网络时，`curl.exe -I https://github.com --connect-timeout 10` 返回 HTTP 200，说明 HTTPS 连通性已经恢复。

### 排查

检查 Git、环境变量和 WinHTTP 代理：

```text
Git global proxy: empty
Git local proxy: empty
HTTP_PROXY / HTTPS_PROXY / ALL_PROXY: empty
WinHTTP proxy: Direct access
```

这说明 Git 没有配置代理，当前是直连 GitHub。由于 `curl` 能访问 GitHub，问题更像短时网络抖动、链路恢复或之前 GitHub 连接路径临时不可达。

### 处理

在连通性恢复后重新执行：

```powershell
git push origin main
```

推送成功：

```text
6142d5b..af59c3e  main -> main
```

### 面试可讲点

网络类发布故障不要只重复 push。先分层确认 DNS、ICMP、TCP 443、HTTP 请求和 Git 代理配置。确认 443 恢复后再重试 push，可以避免把网络问题误判成 GitHub token、仓库权限或代码问题。
