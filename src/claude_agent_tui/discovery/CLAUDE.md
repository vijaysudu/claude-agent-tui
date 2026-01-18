# Discovery Module

## Overview

The `discovery` module provides utilities for discovering, parsing, and monitoring Claude Code sessions and configuration files. It serves as the data ingestion layer for the application, converting raw JSONL session files and configuration files into structured Python objects that can be displayed in the TUI.

This module handles two primary responsibilities:
1. **Session Discovery & Parsing**: Reading and parsing Claude session JSONL files to extract conversation messages, tool uses, and their results
2. **Configuration Discovery**: Scanning the `~/.claude` directory to discover skills, hooks, commands, agents, and MCP servers

## Key Files

### `parser.py`
The core session parsing module that reads Claude session JSONL files and extracts structured data.

**Key Classes:**
- `ParsedToolUse`: Represents a single tool invocation with its parameters and results
- `ParsedMessage`: Represents a conversation message (user or assistant)
- `ParsedSession`: Complete session data including all messages, tool uses, and metadata

**Key Functions:**
- `parse_session(jsonl_path)`: Parse a single session file
- `parse_sessions_in_directory(directory)`: Parse all session files in a directory recursively

### `config_parser.py`
Discovers and parses Claude configuration files from the `~/.claude` directory.

**Key Functions:**
- `discover_all_configs(claude_dir)`: Discover all configuration items at once
- `discover_skills(claude_dir)`: Find all SKILL.md files
- `discover_hooks(claude_dir)`: Parse hooks from settings.json and hooks.json
- `discover_commands(claude_dir)`: Find all command .md files
- `discover_agents(claude_dir)`: Find all AGENT.md files
- `discover_mcp_servers(claude_dir)`: Parse MCP server configurations from settings.json
- `get_claude_dir()`: Get the default `~/.claude` directory path

### `watcher.py`
File system watcher that monitors for changes to session JSONL files in real-time.

**Key Classes:**
- `SessionWatcher`: Monitors a directory for new and modified JSONL files
- `_SessionEventHandler`: Internal handler for file system events

### `__init__.py`
Module exports the primary parsing functions and classes for external use.

**Exports:**
- `parse_session`
- `ParsedToolUse`
- `ParsedSession`
- `SessionWatcher` (optional, requires watchdog)

## Core Data Models

### ParsedToolUse
Represents a single tool invocation extracted from a session.

**Attributes:**
- `tool_use_id`: Unique identifier for the tool call
- `tool_name`: Name of the tool (e.g., "Read", "Bash", "Edit")
- `input_params`: Dictionary of parameters passed to the tool
- `timestamp`: When the tool was invoked
- `result_content`: The tool's output/result
- `error_message`: Error message if the tool failed
- `is_error`: Boolean indicating if the tool call resulted in an error
- `preview`: Auto-generated preview string for display (truncated to 80 chars)

**Preview Generation:**
The `preview` field is automatically generated based on tool type:
- **Read**: Shows the file path
- **Edit/Write**: Shows file path with "(edit)" or "(write)" suffix
- **Bash**: Shows the command (truncated if needed)
- **Grep**: Shows pattern and path
- **Glob**: Shows the pattern
- **Task**: Shows the task description

### ParsedMessage
Represents a conversation message from either the user or assistant.

**Attributes:**
- `uuid`: Message unique identifier
- `role`: "user" or "assistant"
- `timestamp`: When the message was sent
- `text_content`: The text content of the message
- `thinking_content`: Assistant's thinking blocks (extended thinking)
- `tool_use_ids`: List of tool use IDs in this message
- `is_tool_result`: Whether this message contains tool results
- `raw_content`: Original unparsed content

### ParsedSession
Represents a complete Claude session with all its data.

**Attributes:**
- `session_id`: Unique session identifier (derived from filename)
- `session_path`: Path to the JSONL file
- `tool_uses`: List of all tool uses in the session
- `messages`: Complete conversation history
- `message_count`: Total number of messages
- `start_time`: When the session started
- `summary`: Auto-extracted summary (first meaningful user message)
- `project_path`: Working directory/project path for the session

**Properties:**
- `tool_count`: Number of tool uses in the session
- `display_summary`: Truncated summary suitable for list display (max 60 chars)

### ConfigCollection
Container for all discovered configuration items (defined in `store/config_models.py`).

**Attributes:**
- `skills`: List of Skill objects
- `hooks`: List of Hook objects
- `commands`: List of Command objects
- `agents`: List of Agent objects
- `mcp_servers`: List of MCPServer objects

## Usage Examples

### Parsing a Single Session

```python
from claude_agent_tui.discovery import parse_session
from pathlib import Path

# Parse a session file
session_path = Path.home() / ".claude" / "projects" / "-Users-name-project" / "session.jsonl"
session = parse_session(session_path)

# Access session data
print(f"Session: {session.display_summary}")
print(f"Messages: {session.message_count}")
print(f"Tool uses: {session.tool_count}")
print(f"Project: {session.project_path}")

# Iterate over tool uses
for tool_use in session.tool_uses:
    print(f"{tool_use.tool_name}: {tool_use.preview}")
    if tool_use.is_error:
        print(f"  Error: {tool_use.error_message}")
```

### Parsing Multiple Sessions

```python
from claude_agent_tui.discovery.parser import parse_sessions_in_directory
from pathlib import Path

# Parse all sessions in the projects directory
projects_dir = Path.home() / ".claude" / "projects"
sessions = parse_sessions_in_directory(projects_dir)

# Sessions are sorted by start time (newest first)
for session in sessions[:10]:  # Show 10 most recent
    print(f"{session.session_id}: {session.display_summary}")
```

### Watching for Session Changes

```python
from claude_agent_tui.discovery import SessionWatcher
from pathlib import Path

def on_session_changed(path: Path):
    print(f"Session modified: {path}")
    # Re-parse and update UI

def on_new_session(path: Path):
    print(f"New session: {path}")
    # Parse and add to UI

# Start watching
projects_dir = Path.home() / ".claude" / "projects"
watcher = SessionWatcher(
    directory=projects_dir,
    on_change=on_session_changed,
    on_new=on_new_session
)
watcher.start()

# ... run application ...

# Stop when done
watcher.stop()
```

### Discovering Claude Configurations

```python
from claude_agent_tui.discovery.config_parser import (
    discover_all_configs,
    discover_skills,
    get_claude_dir
)

# Discover everything at once
claude_dir = get_claude_dir()
configs = discover_all_configs(claude_dir)

print(f"Found {len(configs.skills)} skills")
print(f"Found {len(configs.agents)} agents")
print(f"Found {len(configs.hooks)} hooks")
print(f"Found {len(configs.mcp_servers)} MCP servers")

# Or discover specific types
skills = discover_skills(claude_dir)
for skill in skills:
    print(f"Skill: {skill.name}")
    if skill.is_from_plugin:
        print(f"  From plugin: {skill.plugin_name}")
```

## Session File Format

The parser expects Claude session files in JSONL (JSON Lines) format, where each line is a JSON object representing an event. The parser handles these entry types:

### Entry Types
- **user**: User messages (may contain text or tool_result blocks)
- **assistant**: Assistant messages (may contain text, thinking, or tool_use blocks)
- **system**: System messages (used to extract project path from context)

### Tool Use Flow
1. Assistant sends a message with `tool_use` blocks
2. Each tool_use has an `id`, `name`, and `input` parameters
3. User responds with `tool_result` blocks containing the same `id`
4. The parser matches results to tool uses by ID and populates the result fields

### Metadata Extraction
- **Project Path**: Extracted from `cwd` field or system message context
- **Summary**: First meaningful user message (excludes meta messages and XML tags)
- **Timestamps**: Extracted from each entry's `timestamp` field

## Configuration File Locations

The config parser searches these locations:

### Skills
- `~/.claude/skills/*/SKILL.md` (standard skills)
- `~/.claude/plugins/*/skills/*/SKILL.md` (plugin skills)

### Hooks
- `~/.claude/settings.json` (under "hooks" key)
- `~/.claude/hooks/hooks.json`

Hook types: UserPromptSubmit, PreToolUse, PostToolUse, Notification, Stop

### Commands
- `~/.claude/commands/*.md`

### Agents
- `~/.claude/agents/*/AGENT.md` (standard agents)
- `~/.claude/plugins/*/agents/*/AGENT.md` (plugin agents)

### MCP Servers
- `~/.claude/settings.json` (under "mcpServers" key)

## Dependencies

### Internal Dependencies
- `store.config_models`: Data models for configuration items (Skill, Hook, Command, Agent, MCPServer, ConfigCollection)

### External Dependencies
- `watchdog`: File system monitoring (optional for SessionWatcher)
  - If not installed, SessionWatcher will not be available but parsing will still work

### Standard Library
- `json`: Parsing JSONL and JSON configuration files
- `pathlib`: Path manipulation
- `dataclasses`: Data class definitions
- `re`: Regular expression parsing for frontmatter
- `asyncio`: Async support (imported but not currently used)

## Integration with Other Modules

### Used By
- **store module**: Manages in-memory storage of parsed sessions and configurations
- **tui module**: Displays parsed session and configuration data in the terminal UI

### Data Flow
1. Discovery module parses raw files → structured Python objects
2. Store module maintains these objects in memory and handles updates
3. TUI module renders the data for user interaction

## Error Handling

The parser is designed to be fault-tolerant:
- **Invalid JSON lines**: Silently skipped (continues parsing)
- **Missing fields**: Uses defaults or None values
- **Malformed files**: Returns partial data or empty structures
- **Subagent sessions**: Automatically filtered out (skips files in "subagents" directories)

This allows the application to function even with corrupted or incomplete session files.

## Performance Considerations

### Session Parsing
- Parses entire file in memory (not streaming)
- Suitable for typical session sizes (hundreds to thousands of lines)
- Large sessions may cause memory spikes

### Directory Scanning
- Uses recursive glob patterns to find files
- May be slow with many session files (hundreds or thousands)
- Results are sorted by timestamp after parsing all files

### Watcher
- Uses OS-level file system events (efficient)
- Minimal overhead when idle
- Callbacks should be non-blocking or use threading
