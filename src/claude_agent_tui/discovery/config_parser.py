"""Parser for Claude configuration files.

Discovers skills, hooks, commands, agents, and MCP servers from Claude's config directory.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..store.config_models import (
    Skill,
    Hook,
    Command,
    Agent,
    MCPServer,
    ConfigCollection,
)


def get_claude_dir() -> Path:
    """Get the Claude configuration directory."""
    return Path.home() / ".claude"


def discover_all_configs(claude_dir: Path | None = None) -> ConfigCollection:
    """Discover all Claude configuration items.

    Args:
        claude_dir: Path to Claude config directory (defaults to ~/.claude).

    Returns:
        ConfigCollection with all discovered config items.
    """
    if claude_dir is None:
        claude_dir = get_claude_dir()

    return ConfigCollection(
        skills=discover_skills(claude_dir),
        hooks=discover_hooks(claude_dir),
        commands=discover_commands(claude_dir),
        agents=discover_agents(claude_dir),
        mcp_servers=discover_mcp_servers(claude_dir),
    )


def discover_skills(claude_dir: Path) -> list[Skill]:
    """Discover skills from ~/.claude/skills/*/SKILL.md.

    Also discovers skills from plugins: ~/.claude/plugins/*/skills/*/SKILL.md

    Args:
        claude_dir: Path to Claude config directory.

    Returns:
        List of discovered skills.
    """
    skills: list[Skill] = []

    # Standard skills location
    skills_dir = claude_dir / "skills"
    if skills_dir.exists():
        for skill_file in skills_dir.glob("*/SKILL.md"):
            skill = _parse_skill_file(skill_file)
            if skill:
                skills.append(skill)

    # Plugin skills
    plugins_dir = claude_dir / "plugins"
    if plugins_dir.exists():
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir():
                plugin_skills_dir = plugin_dir / "skills"
                if plugin_skills_dir.exists():
                    for skill_file in plugin_skills_dir.glob("*/SKILL.md"):
                        skill = _parse_skill_file(skill_file, plugin_name=plugin_dir.name)
                        if skill:
                            skills.append(skill)

    return sorted(skills, key=lambda s: s.name.lower())


def _parse_skill_file(skill_file: Path, plugin_name: str | None = None) -> Skill | None:
    """Parse a SKILL.md file.

    Args:
        skill_file: Path to the SKILL.md file.
        plugin_name: Name of the plugin if this is a plugin skill.

    Returns:
        Parsed Skill or None if parsing failed.
    """
    try:
        content = skill_file.read_text(encoding="utf-8")
        name = skill_file.parent.name
        description = ""

        # Try to parse frontmatter for description
        frontmatter = _parse_frontmatter(content)
        if frontmatter:
            description = frontmatter.get("description", "")
            if "name" in frontmatter:
                name = frontmatter["name"]

        # Fallback: get first non-frontmatter line as description
        if not description:
            lines = content.split("\n")
            in_frontmatter = False
            for line in lines:
                if line.strip() == "---":
                    in_frontmatter = not in_frontmatter
                    continue
                if not in_frontmatter and line.strip() and not line.startswith("#"):
                    description = line.strip()[:100]
                    break

        return Skill(
            name=name,
            description=description,
            file_path=skill_file,
            content=content,
            is_from_plugin=plugin_name is not None,
            plugin_name=plugin_name,
        )
    except Exception:
        return None


def discover_hooks(claude_dir: Path) -> list[Hook]:
    """Discover hooks from settings.json and hooks.json.

    Hooks can be defined in:
    - ~/.claude/settings.json under "hooks" key
    - ~/.claude/hooks/hooks.json

    Args:
        claude_dir: Path to Claude config directory.

    Returns:
        List of discovered hooks.
    """
    hooks: list[Hook] = []

    # Check settings.json
    settings_path = claude_dir / "settings.json"
    if settings_path.exists():
        hooks.extend(_parse_hooks_from_file(settings_path))

    # Check hooks.json
    hooks_path = claude_dir / "hooks" / "hooks.json"
    if hooks_path.exists():
        hooks.extend(_parse_hooks_from_file(hooks_path))

    return hooks


def _parse_hooks_from_file(file_path: Path) -> list[Hook]:
    """Parse hooks from a JSON file.

    Args:
        file_path: Path to the JSON file.

    Returns:
        List of parsed hooks.
    """
    hooks: list[Hook] = []

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))

        # Get hooks section (might be top-level or under "hooks" key)
        hooks_data = data.get("hooks", data)

        # Hooks are organized by type (UserPromptSubmit, PostToolUse, etc.)
        hook_types = [
            "UserPromptSubmit",
            "PreToolUse",
            "PostToolUse",
            "Notification",
            "Stop",
        ]

        for hook_type in hook_types:
            if hook_type in hooks_data:
                hook_entries = hooks_data[hook_type]
                if isinstance(hook_entries, list):
                    for entry in hook_entries:
                        hook = _parse_hook_entry(hook_type, entry)
                        if hook:
                            hooks.append(hook)
                elif isinstance(hook_entries, dict):
                    hook = _parse_hook_entry(hook_type, hook_entries)
                    if hook:
                        hooks.append(hook)

    except Exception:
        pass

    return hooks


def _parse_hook_entry(hook_type: str, entry: dict[str, Any]) -> Hook | None:
    """Parse a single hook entry.

    Args:
        hook_type: The type of hook (e.g., "UserPromptSubmit").
        entry: The hook entry dictionary.

    Returns:
        Parsed Hook or None if invalid.
    """
    try:
        command = entry.get("command", "")
        if not command:
            # Some hooks use "hooks" as an array of commands
            hooks_list = entry.get("hooks", [])
            if hooks_list:
                commands = []
                for h in hooks_list:
                    if isinstance(h, dict):
                        commands.append(h.get("command", ""))
                    elif isinstance(h, str):
                        commands.append(h)
                command = " && ".join([c for c in commands if c])

        if not command:
            return None

        matcher = entry.get("matcher")
        timeout = entry.get("timeout")

        return Hook(
            hook_type=hook_type,
            command=command,
            matcher=matcher,
            timeout=timeout,
        )
    except Exception:
        return None


def discover_commands(claude_dir: Path) -> list[Command]:
    """Discover custom commands from ~/.claude/commands/*.md.

    Args:
        claude_dir: Path to Claude config directory.

    Returns:
        List of discovered commands.
    """
    commands: list[Command] = []

    commands_dir = claude_dir / "commands"
    if commands_dir.exists():
        for cmd_file in commands_dir.glob("*.md"):
            command = _parse_command_file(cmd_file)
            if command:
                commands.append(command)

    return sorted(commands, key=lambda c: c.name.lower())


def _parse_command_file(cmd_file: Path) -> Command | None:
    """Parse a command markdown file.

    Args:
        cmd_file: Path to the command file.

    Returns:
        Parsed Command or None if parsing failed.
    """
    try:
        content = cmd_file.read_text(encoding="utf-8")
        name = cmd_file.stem  # filename without .md
        description = ""

        # Try to parse frontmatter for description
        frontmatter = _parse_frontmatter(content)
        if frontmatter:
            description = frontmatter.get("description", "")
            if "name" in frontmatter:
                name = frontmatter["name"]

        # Fallback: get first heading or first line as description
        if not description:
            lines = content.split("\n")
            in_frontmatter = False
            for line in lines:
                if line.strip() == "---":
                    in_frontmatter = not in_frontmatter
                    continue
                if not in_frontmatter and line.strip():
                    if line.startswith("#"):
                        description = line.lstrip("#").strip()[:100]
                    else:
                        description = line.strip()[:100]
                    break

        return Command(
            name=name,
            description=description,
            file_path=cmd_file,
            content=content,
        )
    except Exception:
        return None


def discover_agents(claude_dir: Path) -> list[Agent]:
    """Discover agents from ~/.claude/agents/*/AGENT.md.

    Also discovers agents from plugins: ~/.claude/plugins/*/agents/*/AGENT.md

    Args:
        claude_dir: Path to Claude config directory.

    Returns:
        List of discovered agents.
    """
    agents: list[Agent] = []

    # Standard agents location
    agents_dir = claude_dir / "agents"
    if agents_dir.exists():
        for agent_file in agents_dir.glob("*/AGENT.md"):
            agent = _parse_agent_file(agent_file)
            if agent:
                agents.append(agent)

    # Plugin agents
    plugins_dir = claude_dir / "plugins"
    if plugins_dir.exists():
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir():
                plugin_agents_dir = plugin_dir / "agents"
                if plugin_agents_dir.exists():
                    for agent_file in plugin_agents_dir.glob("*/AGENT.md"):
                        agent = _parse_agent_file(agent_file, plugin_name=plugin_dir.name)
                        if agent:
                            agents.append(agent)

    return sorted(agents, key=lambda a: a.name.lower())


def _parse_agent_file(agent_file: Path, plugin_name: str | None = None) -> Agent | None:
    """Parse an AGENT.md file.

    Args:
        agent_file: Path to the AGENT.md file.
        plugin_name: Name of the plugin if this is a plugin agent.

    Returns:
        Parsed Agent or None if parsing failed.
    """
    try:
        content = agent_file.read_text(encoding="utf-8")
        name = agent_file.parent.name
        description = ""
        tools: list[str] = []
        model = "inherit"
        color = None

        # Parse frontmatter
        frontmatter = _parse_frontmatter(content)
        if frontmatter:
            description = frontmatter.get("description", "")
            if "name" in frontmatter:
                name = frontmatter["name"]
            if "tools" in frontmatter:
                tools_val = frontmatter["tools"]
                if isinstance(tools_val, list):
                    tools = tools_val
                elif isinstance(tools_val, str):
                    tools = [t.strip() for t in tools_val.split(",")]
            if "model" in frontmatter:
                model = frontmatter["model"]
            if "color" in frontmatter:
                color = frontmatter["color"]

        return Agent(
            name=name,
            description=description,
            tools=tools,
            model=model,
            file_path=agent_file,
            content=content,
            is_from_plugin=plugin_name is not None,
            plugin_name=plugin_name,
            color=color,
        )
    except Exception:
        return None


def discover_mcp_servers(claude_dir: Path) -> list[MCPServer]:
    """Discover MCP servers from settings.json.

    Args:
        claude_dir: Path to Claude config directory.

    Returns:
        List of discovered MCP servers.
    """
    servers: list[MCPServer] = []

    settings_path = claude_dir / "settings.json"
    if not settings_path.exists():
        return servers

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        mcp_servers = data.get("mcpServers", {})

        for name, config in mcp_servers.items():
            if isinstance(config, dict):
                server = MCPServer(
                    name=name,
                    command=config.get("command", ""),
                    args=config.get("args", []),
                    env=config.get("env", {}),
                    cwd=config.get("cwd"),
                )
                servers.append(server)

    except Exception:
        pass

    return sorted(servers, key=lambda s: s.name.lower())


def _parse_frontmatter(content: str) -> dict[str, Any] | None:
    """Parse YAML frontmatter from markdown content.

    Args:
        content: The markdown content.

    Returns:
        Dictionary of frontmatter values or None if no frontmatter.
    """
    # Match frontmatter between --- markers
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    frontmatter_text = match.group(1)
    result: dict[str, Any] = {}

    # Simple YAML-like parsing (key: value or key: [list])
    current_key = None
    current_list: list[str] = []

    for line in frontmatter_text.split("\n"):
        line = line.rstrip()
        if not line:
            continue

        # Check for list item
        if line.startswith("  - ") or line.startswith("- "):
            if current_key:
                item = line.lstrip(" -").strip()
                current_list.append(item)
            continue

        # Check for key: value
        if ":" in line:
            # Save previous list if any
            if current_key and current_list:
                result[current_key] = current_list
                current_list = []

            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            if value:
                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                result[key] = value
                current_key = None
            else:
                # Value might be a list on following lines
                current_key = key

    # Save final list if any
    if current_key and current_list:
        result[current_key] = current_list

    return result if result else None
