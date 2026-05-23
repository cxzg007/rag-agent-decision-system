import json
import logging
from functools import lru_cache
from pathlib import Path

from app.schemas.skill import MCPServerDefinition, SkillDefinition


logger = logging.getLogger(__name__)

SKILL_CONFIG_DIR = Path("config/skills")
MCP_CONFIG_DIR = Path("config/mcp_servers")


@lru_cache(maxsize=1)
def load_skill_definitions() -> dict[str, SkillDefinition]:
    return _load_config_dir(SKILL_CONFIG_DIR, SkillDefinition, "skill_id")


@lru_cache(maxsize=1)
def load_mcp_server_definitions() -> dict[str, MCPServerDefinition]:
    return _load_config_dir(MCP_CONFIG_DIR, MCPServerDefinition, "server_id")


def reload_skill_and_mcp_registries() -> tuple[dict[str, SkillDefinition], dict[str, MCPServerDefinition]]:
    load_skill_definitions.cache_clear()
    load_mcp_server_definitions.cache_clear()
    return load_skill_definitions(), load_mcp_server_definitions()


def get_skill_definition(skill_id: str) -> SkillDefinition:
    try:
        return load_skill_definitions()[skill_id]
    except KeyError as exc:
        raise ValueError(f"unknown skill_id: {skill_id}") from exc


def get_mcp_server_definition(server_id: str) -> MCPServerDefinition:
    try:
        return load_mcp_server_definitions()[server_id]
    except KeyError as exc:
        raise ValueError(f"unknown mcp server_id: {server_id}") from exc


def validate_skill_links() -> list[str]:
    errors: list[str] = []
    mcp_servers = load_mcp_server_definitions()
    for skill in load_skill_definitions().values():
        if skill.skill_path and not Path(skill.skill_path).exists():
            errors.append(f"skill {skill.skill_id} has missing skill_path: {skill.skill_path}")
        if skill.instructions_path and not Path(skill.instructions_path).is_file():
            errors.append(f"skill {skill.skill_id} has missing instructions_path: {skill.instructions_path}")
        for server_id in skill.mcp_servers:
            if server_id not in mcp_servers:
                errors.append(f"skill {skill.skill_id} references unknown mcp server: {server_id}")
    for server in mcp_servers.values():
        if server.transport == "stdio" and server.enabled and not server.command:
            errors.append(f"mcp server {server.server_id} uses stdio but command is missing")
        if server.transport == "http" and server.enabled and not server.url:
            errors.append(f"mcp server {server.server_id} uses http but url is missing")
        server_scopes = set(server.allowed_tool_scopes)
        if server_scopes:
            for tool in server.tools:
                if tool.scope not in server_scopes:
                    errors.append(
                        f"mcp server {server.server_id} tool {tool.name} has scope outside allowed_tool_scopes: {tool.scope}"
                    )
    return errors


def _load_config_dir(path: Path, model_type, id_field: str) -> dict:
    definitions = {}
    if not path.exists():
        return definitions
    for file_path in sorted(path.glob("*.json")):
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            item = model_type.model_validate(payload)
            definitions[getattr(item, id_field)] = item
        except Exception as exc:
            logger.warning("failed to load config %s: %s", file_path, exc)
    return definitions
