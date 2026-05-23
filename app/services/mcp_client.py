import asyncio
import json
import time
from typing import Any

import httpx
from pydantic import BaseModel, create_model

from app.core.security import security_context
from app.schemas.skill import MCPServerDefinition, MCPToolDefinition
from app.tools.registry import get_tool_spec


class MCPExecutionError(RuntimeError):
    pass


class MCPClient:
    async def call_tool(self, server: MCPServerDefinition, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        tool = self._resolve_tool(server, tool_name)
        self._validate_server(server)
        self._validate_scope(server, tool)
        self._validate_arguments(tool, arguments)

        if server.transport == "internal":
            result = await self._call_internal(tool_name, arguments, timeout_seconds=server.timeout_seconds)
        elif server.transport == "stdio":
            result = await self._call_stdio(server, tool_name, arguments)
        elif server.transport == "http":
            result = await self._call_http(server, tool_name, arguments)
        elif server.transport == "sse":
            raise MCPExecutionError("sse MCP transport is not implemented yet")
        else:
            raise MCPExecutionError(f"unsupported MCP transport: {server.transport}")

        return {
            "server_id": server.server_id,
            "tool_name": tool_name,
            "transport": server.transport,
            "result": result,
            "latency_ms": (time.perf_counter() - started) * 1000,
        }

    def _resolve_tool(self, server: MCPServerDefinition, tool_name: str) -> MCPToolDefinition:
        for tool in server.tools:
            if tool.name == tool_name:
                return tool
        raise MCPExecutionError(f"unknown MCP tool {tool_name!r} for server {server.server_id!r}")

    def _validate_server(self, server: MCPServerDefinition) -> None:
        if not server.enabled:
            raise MCPExecutionError(f"MCP server is disabled: {server.server_id}")
        if server.transport == "stdio" and not server.command:
            raise MCPExecutionError("stdio MCP server requires command")
        if server.transport == "http" and not server.url:
            raise MCPExecutionError("http MCP server requires url")

    def _validate_scope(self, server: MCPServerDefinition, tool: MCPToolDefinition) -> None:
        context = security_context()
        if tool.scope not in context.allowed_tool_scopes:
            raise PermissionError(f"MCP tool scope not allowed: {tool.scope}")
        if server.allowed_tool_scopes and tool.scope not in set(server.allowed_tool_scopes):
            raise PermissionError(f"MCP tool scope not allowed by server config: {tool.scope}")

    def _validate_arguments(self, tool: MCPToolDefinition, arguments: dict[str, Any]) -> None:
        schema = tool.input_schema or {}
        required = schema.get("required", [])
        missing = [name for name in required if name not in arguments]
        if missing:
            raise ValueError(f"missing required MCP tool argument(s): {', '.join(missing)}")
        properties = schema.get("properties", {})
        fields = {}
        for name, definition in properties.items():
            fields[name] = (self._python_type(definition.get("type")), None)
        if fields:
            model = create_model(f"{tool.name.title().replace('_', '')}MCPInput", **fields)
            model.model_validate(arguments)

    def _python_type(self, json_type: str | None):
        if json_type == "string":
            return str
        if json_type == "integer":
            return int
        if json_type == "number":
            return float
        if json_type == "boolean":
            return bool
        if json_type == "array":
            return list
        if json_type == "object":
            return dict
        return Any

    async def _call_internal(self, tool_name: str, arguments: dict[str, Any], timeout_seconds: float) -> Any:
        spec = get_tool_spec(tool_name)
        payload = spec.input_model.model_validate(arguments)
        output = await asyncio.wait_for(spec.handler(payload), timeout=timeout_seconds)
        if isinstance(output, BaseModel):
            return output.model_dump()
        return output

    async def _call_http(self, server: MCPServerDefinition, tool_name: str, arguments: dict[str, Any]) -> Any:
        payload = self._json_rpc_payload(tool_name, arguments)
        timeout = httpx.Timeout(server.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, headers=server.headers, trust_env=False) as client:
            response = await client.post(server.url, json=payload)
            response.raise_for_status()
            return self._extract_json_rpc_result(response.json())

    async def _call_stdio(self, server: MCPServerDefinition, tool_name: str, arguments: dict[str, Any]) -> Any:
        process = await asyncio.create_subprocess_exec(
            server.command,
            *server.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await self._stdio_request(process, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "agent-mcp-client", "version": "0.1.0"}}, timeout=server.timeout_seconds)
            await self._stdio_notification(process, "notifications/initialized", {})
            return await self._stdio_request(
                process,
                "tools/call",
                {"name": tool_name, "arguments": arguments},
                timeout=server.timeout_seconds,
            )
        finally:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

    async def _stdio_request(self, process, method: str, params: dict[str, Any], timeout: float) -> Any:
        message_id = int(time.time() * 1000)
        await self._write_stdio_message(process, {"jsonrpc": "2.0", "id": message_id, "method": method, "params": params})
        while True:
            message = await asyncio.wait_for(self._read_stdio_message(process), timeout=timeout)
            if message.get("id") == message_id:
                return self._extract_json_rpc_result(message)

    async def _stdio_notification(self, process, method: str, params: dict[str, Any]) -> None:
        await self._write_stdio_message(process, {"jsonrpc": "2.0", "method": method, "params": params})

    async def _write_stdio_message(self, process, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        process.stdin.write(header + body)
        await process.stdin.drain()

    async def _read_stdio_message(self, process) -> dict[str, Any]:
        headers: dict[str, str] = {}
        while True:
            line = await process.stdout.readline()
            if not line:
                stderr = await process.stderr.read()
                error = stderr.decode("utf-8", errors="replace").strip()
                raise MCPExecutionError(f"MCP stdio server closed stdout: {error}")
            line_text = line.decode("ascii", errors="replace").strip()
            if not line_text:
                break
            if ":" in line_text:
                key, value = line_text.split(":", 1)
                headers[key.lower()] = value.strip()
        content_length = int(headers.get("content-length", "0"))
        if content_length <= 0:
            raise MCPExecutionError("MCP stdio response missing Content-Length")
        body = await process.stdout.readexactly(content_length)
        return json.loads(body.decode("utf-8"))

    def _json_rpc_payload(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

    def _extract_json_rpc_result(self, payload: dict[str, Any]) -> Any:
        if "error" in payload and payload["error"]:
            raise MCPExecutionError(str(payload["error"]))
        if "result" not in payload:
            raise MCPExecutionError("MCP response missing result")
        return payload["result"]


mcp_client = MCPClient()
