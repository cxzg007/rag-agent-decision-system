# Skill 与 MCP 设计

## 1. 设计目标

本项目将 Skill 和 MCP 设计成 Agent 能力层的两个边界：

```text
Skill = 能力包，类似 FastAPI 的 APIRouter
MCP Server = 外部工具提供方，类似 FastAPI 的 dependency/provider
Tool = 具体可执行能力
Workflow = Skill 默认绑定的执行图
```

这样做的目标是：

- 不把所有工具直接暴露给 LLM
- Skill 可以声明它需要哪些 workflow、tool scope 和 MCP server
- MCP server 可以单独声明 transport、工具列表、权限范围和启用状态
- 后续接真实 stdio/http/sse MCP client 时，有清晰安全边界

## 2. Skill 配置

配置目录：

```text
config/skills
```

项目内可复用的 Codex-style skill 本体放在：

```text
skills/<skill-name>/SKILL.md
skills/<skill-name>/references/*
skills/<skill-name>/agents/openai.yaml
```

`config/skills/*.json` 负责让后端 registry 发现这个 skill；`skills/<skill-name>/SKILL.md` 负责给 Codex/Agent 提供具体执行流程和知识入口。

示例：

```json
{
  "skill_id": "rag_research",
  "name": "RAG Research Agent",
  "workflow_id": "rag_multi_agent_v1",
  "allowed_tool_scopes": ["retrieval", "memory", "planning"],
  "mcp_servers": ["local_agent_tools"],
  "enabled": true
}
```

字段含义：

- `skill_id`: Skill 唯一 ID
- `skill_path`: 项目内 skill 文件夹，例如 `skills/resume-writer`
- `instructions_path`: skill 主说明文件，例如 `skills/resume-writer/SKILL.md`
- `workflow_id`: 默认执行 workflow
- `allowed_tool_scopes`: 该 skill 允许使用的工具范围
- `mcp_servers`: 该 skill 关联的 MCP server
- `default_inputs`: 默认 top_k / LLM 开关等参数
- `tags`: 检索和分类用标签

## 3. MCP Server 配置

配置目录：

```text
config/mcp_servers
```

示例：

```json
{
  "server_id": "local_agent_tools",
  "transport": "internal",
  "enabled": true,
  "allowed_tool_scopes": ["retrieval", "memory", "planning"],
  "tools": [
    {
      "name": "knowledge_search",
      "scope": "retrieval",
      "input_schema": {"type": "object"}
    }
  ]
}
```

MVP 第一版只实现了 MCP-style catalog；当前版本已经在同一个 registry 边界后补充真实 MCP client。

当前已补充真实执行入口：

```text
POST /mcp/servers/{server_id}/tools/{tool_name}/call
```

支持：

- `internal`: 复用本项目 `ToolRegistry`
- `stdio`: 启动外部 MCP stdio server，按 JSON-RPC `initialize` + `tools/call` 调用
- `http`: 向配置的 URL 发送 JSON-RPC `tools/call`

暂不支持：

- `sse`: 当前会返回明确错误，避免假装支持长连接协议

Agent 内部也支持工具名：

```text
mcp:<server_id>:<tool_name>
```

后续 LLM Planner 可以把 MCP tool schema 转成可选工具，但执行时仍走 scope 和 registry 校验。

外部 MCP 工具通常使用 `external` scope，默认不在 `ALLOWED_TOOL_SCOPES` 中。需要显式开启：

```powershell
$env:ALLOWED_TOOL_SCOPES="retrieval,memory,planning,external"
```

## 4. API

```text
GET  /skills
GET  /skills/{skill_id}
POST /skills/reload

GET  /mcp/servers
GET  /mcp/servers/{server_id}
POST /mcp/reload
```

reload 接口受 API Key 保护。

## 5. 安全边界

当前策略：

- MCP server 默认只是 catalog，不直接执行外部命令
- reload 是管理操作，需要 API Key
- Skill 引用的 MCP server 会做存在性校验
- Tool 真正执行仍走 `ToolSpec.scope` 和 `ALLOWED_TOOL_SCOPES`

后续接真实 MCP 时需要补：

- sse transport client
- 每个 MCP server 的 allowlist
- 工具调用审计
- 参数 schema 强校验
- 超时、重试和熔断
- 禁止任意命令执行

## 6. 面试讲法

可以这样讲：

> 我没有把 MCP 工具直接暴露给 Agent，而是参考 FastAPI 的 router/dependency 思路，先做 SkillRegistry 和 MCPRegistry。Skill 像一个能力包，声明默认 workflow 和允许的工具范围；MCP server 像外部工具 provider，声明 transport、工具 schema 和权限边界。真正执行工具时仍走 ToolExecutor 的 scope 校验。这样后续接真实 MCP client 时，不会破坏现有安全模型。
