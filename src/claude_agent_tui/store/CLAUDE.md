# Claude Agent Viz - Store Module

## Overview

The `store` module provides the core data models and state management structures for the Claude Agent Visualization tool. It defines the data schemas used throughout the application to represent Claude sessions, tool executions, configuration items, and conversation messages.

This module serves as the single source of truth for data structures, ensuring type safety and consistency across the TUI, discovery, and state management components.

## Purpose

The store module provides:
1. **Session Models**: Track Claude agent sessions, including conversation history, tool usage, and metadata
2. **Tool Execution Models**: Represent individual tool invocations with their parameters, status, and results
3. **Configuration Models**: Define Claude configuration items like skills, hooks, commands, agents, and MCP servers
4. **Message Models**: Structure conversation messages with support for thinking blocks and tool results

## Key Files

### `__init__.py`
- **Purpose**: Package initialization and public API definition
- **Exports**:
  - `Session`: Main session data model
  - `ToolUse`: Tool execution representation
  - `ToolStatus`: Enum for tool execution states

### `models.py`
- **Purpose**: Core data models for sessions, tools, and messages
- **Key Classes**:
  - `Session`: Represents a complete Claude session with conversation and tool history
  - `ToolUse`: Individual tool execution with parameters and results
  - `ConversationMessage`: Message in the conversation thread
  - `ToolStatus`: Enum for tool states (PENDING, RUNNING, COMPLETED, ERROR)
  - `MessageRole`: Enum for message roles (USER, ASSISTANT)

### `config_models.py`
- **Purpose**: Data models for Claude configuration items
- **Key Classes**:
  - `Skill`: Claude skill configuration
  - `Hook`: Event hook configuration
  - `Command`: Custom command definition
  - `Agent`: Agent configuration with tools and model
  - `MCPServer`: Model Context Protocol server configuration
  - `ConfigCollection`: Container for all configuration types

## Important Classes

### Session

Represents a Claude agent session with full conversation and tool execution history.

**Key Attributes**:
- `session_id`: Unique identifier for the session
- `session_path`: Path to session data directory
- `tool_uses`: List of all tool executions in this session
- `messages`: Complete conversation history
- `message_count`: Number of messages exchanged
- `start_time`: Session start timestamp
- `is_active`: Whether the session is currently running
- `pid`: Process ID if session is active
- `summary`: Brief description (typically first user message)
- `project_path`: Working directory for the session

**Key Properties**:
- `tool_count`: Returns number of tool executions
- `display_name`: Short session identifier (first 8 chars of ID)
- `display_summary`: Truncated summary for UI display (max 60 chars)
- `project_name`: Project directory name

**Key Methods**:
- `get_tool_by_id(tool_use_id)`: Retrieve a specific tool execution by ID

### ToolUse

Represents a single tool execution within a session.

**Key Attributes**:
- `tool_use_id`: Unique identifier
- `tool_name`: Name of the tool (e.g., "Read", "Edit", "Bash")
- `input_params`: Dictionary of input parameters
- `status`: Execution status (ToolStatus enum)
- `preview`: Short preview of tool execution
- `duration_ms`: Execution time in milliseconds
- `timestamp`: When the tool was executed
- `result_content`: Output from the tool
- `error_message`: Error details if execution failed

**Key Methods**:
- `get_file_path()`: Extract file path for file-operation tools (Read, Edit, Write, Grep, Glob)
- `get_display_name()`: Generate human-readable display name based on tool type and parameters

### ConversationMessage

Represents a single message in the conversation thread.

**Key Attributes**:
- `uuid`: Unique message identifier
- `role`: MessageRole (USER or ASSISTANT)
- `timestamp`: When the message was sent
- `text_content`: Extracted text content
- `thinking_content`: Claude's thinking block content (assistant only)
- `tool_use_ids`: List of tool execution IDs referenced in this message
- `is_tool_result`: Whether this message contains tool results
- `raw_content`: Original content for advanced rendering

### ConfigCollection

Container for all Claude configuration items.

**Attributes**:
- `skills`: List of Skill objects
- `hooks`: List of Hook objects
- `commands`: List of Command objects
- `agents`: List of Agent objects
- `mcp_servers`: List of MCPServer objects

## Usage Examples

### Working with Sessions

```python
from claude_agent_tui.store import Session, ToolUse, ToolStatus
from pathlib import Path

# Create a new session
session = Session(
    session_id="abc123def456",
    session_path=Path("/path/to/session"),
    summary="Implement feature X",
    project_path="/path/to/project",
    is_active=True
)

# Access session properties
print(session.display_name)  # "abc123de"
print(session.display_summary)  # "Implement feature X"
print(session.tool_count)  # 0

# Add a tool use
tool = ToolUse(
    tool_use_id="tool_001",
    tool_name="Read",
    input_params={"file_path": "/path/to/file.py"},
    status=ToolStatus.COMPLETED,
    result_content="file contents..."
)
session.tool_uses.append(tool)

# Retrieve a tool by ID
retrieved_tool = session.get_tool_by_id("tool_001")
```

### Working with Tool Executions

```python
# Create a tool use
bash_tool = ToolUse(
    tool_use_id="tool_002",
    tool_name="Bash",
    input_params={"command": "pytest tests/"},
    status=ToolStatus.RUNNING,
    timestamp="2024-01-15T10:30:00Z"
)

# Get display name
print(bash_tool.get_display_name())  # "Bash: pytest"

# Check if it operates on a file
file_path = bash_tool.get_file_path()  # None (Bash doesn't operate on files)

# Update status when complete
bash_tool.status = ToolStatus.COMPLETED
bash_tool.result_content = "All tests passed"
bash_tool.duration_ms = 1500
```

### Working with Configuration Models

```python
from claude_agent_tui.store.config_models import (
    Skill, Agent, MCPServer, ConfigCollection
)
from pathlib import Path

# Create a skill
skill = Skill(
    name="debug",
    description="Debug Python code",
    file_path=Path("/path/to/skill.md"),
    content="# Debug Skill\n...",
    is_from_plugin=False
)

# Create an agent
agent = Agent(
    name="code-reviewer",
    description="Reviews code for quality",
    tools=["Read", "Grep", "LSP"],
    model="claude-opus-4",
    file_path=Path("/path/to/agent.yaml"),
    content="...",
    color="#FF5733"
)

# Create an MCP server
mcp_server = MCPServer(
    name="github",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-github"],
    env={"GITHUB_TOKEN": "..."}
)

print(mcp_server.full_command)  # "npx -y @modelcontextprotocol/server-github"

# Create a collection
config = ConfigCollection(
    skills=[skill],
    agents=[agent],
    mcp_servers=[mcp_server]
)
```

## Dependencies and Relationships

### Internal Dependencies
The store module is imported and used by:

1. **TUI Components** (`claude_agent_tui.tui.*`):
   - `app.py`: Main application uses Session and ToolUse
   - `widgets/session_list.py`: Displays Session objects
   - `widgets/tool_list.py`: Displays ToolUse objects
   - `widgets/detail_panel.py`: Shows detailed Session/ToolUse information

2. **State Management** (`claude_agent_tui.state`):
   - Uses Session and ToolUse for application state

3. **Discovery Module** (`claude_agent_tui.discovery`):
   - Imports and populates Session objects from filesystem

4. **Demo Module** (`claude_agent_tui.demo`):
   - Creates sample Session and ToolUse objects for testing

### External Dependencies
- **Python Standard Library**:
  - `dataclasses`: For data class definitions
  - `enum`: For status enumerations
  - `pathlib`: For file path handling
  - `typing`: For type annotations

### Design Patterns
- **Data Transfer Objects (DTO)**: All models are immutable data containers
- **Enum Pattern**: Status and role enums for type safety
- **Property Pattern**: Computed properties for derived data (display_name, tool_count, etc.)

## Type Safety

All models use Python type hints extensively:
- `from __future__ import annotations`: Enable forward references
- Union types: `str | None` for optional values
- Generic types: `list[ToolUse]`, `dict[str, Any]`
- Type aliases: Clean type definitions

## Best Practices

1. **Use Enums**: Always use `ToolStatus` and `MessageRole` enums instead of strings
2. **Immutable After Creation**: Treat dataclass instances as mostly immutable after initialization
3. **Factory Defaults**: Lists and dicts use `field(default_factory=...)` to avoid mutable defaults
4. **Path Objects**: Use `pathlib.Path` for file paths, not strings
5. **Type Hints**: Always include type hints when working with these models
6. **Display Methods**: Use `display_name` and `display_summary` properties for UI rendering

## Extension Points

To extend the store module:

1. **Add New Tool Types**: Update `ToolUse.get_file_path()` and `get_display_name()` methods
2. **Add New Configuration Types**: Create new dataclass in `config_models.py` and add to `ConfigCollection`
3. **Add Session Metadata**: Add new fields to `Session` dataclass
4. **Add Message Types**: Extend `ConversationMessage` for new content types

## Notes

- The module uses dataclasses for clean, declarative data models
- All timestamps are stored as ISO 8601 strings for serialization
- File paths are stored as `pathlib.Path` objects internally
- The module has no external dependencies beyond Python standard library
- Models are designed for easy JSON serialization/deserialization
