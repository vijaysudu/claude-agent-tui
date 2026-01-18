# Claude Agent Visualizer - Root Module

## Overview

The `claude_agent_tui` package is the root module for the Claude Agent Visualizer, a terminal user interface (TUI) application that allows you to visualize, monitor, and interact with Claude Code agent sessions. This tool provides real-time insights into Claude's tool usage, conversation flow, and session management capabilities.

## Purpose

This module serves as the foundation for:
- Discovering and parsing Claude session JSONL files from `~/.claude/projects`
- Managing application state across sessions, tool uses, and configurations
- Detecting active Claude processes and associating them with sessions
- Providing a CLI entry point for launching the TUI
- Managing process lifecycle for spawned Claude sessions

## Key Files

### Core Module Files

#### `__init__.py`
- **Purpose**: Package initialization and version definition
- **Exports**: `__version__ = "0.1.0"`
- **Usage**: Import version info with `from claude_agent_tui import __version__`

#### `__main__.py`
- **Purpose**: Primary entry point for the application
- **Key Function**: `main() -> int` - Parses CLI arguments and launches the TUI
- **Command-line Arguments**:
  - `--demo`: Run with demo data instead of real sessions
  - `--sessions-dir, -d`: Custom directory containing session JSONL files
  - `--version`: Display version information
- **Usage**: Executed via `python -m claude_agent_tui` or the `claude-tui` command

#### `cli.py`
- **Purpose**: CLI wrapper module that re-exports the main function
- **Usage**: Alternative import path for the main CLI entry point
- **Note**: Primarily for module organization; delegates to `__main__.main()`

#### `state.py`
- **Purpose**: Centralized application state management
- **Key Classes**:
  - `AppState`: Main state container holding sessions, configurations, and UI state
- **Key Functions**:
  - `get_current_session_ids()`: Reads `~/.claude/history.jsonl` to find active sessions
  - `get_active_claude_processes()`: Uses system commands to find running Claude instances
  - `get_active_claude_directories()`: Returns directories where Claude is currently running
  - `convert_parsed_session()`: Converts parsed JSONL data to Session models
- **State Management**:
  - Tracks selected sessions and tools
  - Manages spawn mode (embedded/external)
  - Handles active session filtering
  - Provides observer pattern with update listeners
  - Tracks spawned process PIDs for cleanup

#### `process.py`
- **Purpose**: Low-level process management for Claude sessions
- **Key Classes**:
  - `ClaudeProcess`: Dataclass representing a running Claude process
    - `pid`: Process ID
    - `cwd`: Working directory
    - `command`: Full command line
    - `session_id`: Associated session identifier
- **Key Functions**:
  - `find_claude_processes()`: Discovers all running Claude processes using `ps`
  - `get_process_cwd()`: Retrieves working directory for a PID using `lsof`
  - `extract_session_id()`: Heuristically matches processes to session files
  - `kill_process()`: Terminates a process by PID (SIGTERM or SIGKILL)
  - `kill_session()`: Kills a Claude session by session ID
  - `kill_by_pid()`: Kills a process after verifying it's a Claude process
  - `get_session_pid()`: Finds PID for a given session path
  - `is_session_running()`: Checks if session is active (recent file modification or process exists)
- **Platform Support**: Primarily designed for macOS/Unix systems using `ps` and `lsof`

#### `demo.py`
- **Purpose**: Provides sample data for testing and demonstration
- **Key Functions**:
  - `create_demo_sessions()`: Generates 3 complete demo sessions with tool uses
- **Demo Data**:
  - Sample Python, Bash, and Grep outputs
  - Three scenarios: feature implementation, bug fix, and code review
  - Includes completed and error tool statuses
- **Usage**: Activated with `claude-tui --demo` flag

## Important Classes and Concepts

### AppState Class

The `AppState` class is the heart of the application's data management:

```python
@dataclass
class AppState:
    # Session data
    sessions: list[Session]
    selected_session_id: str | None
    selected_tool_id: str | None

    # Configuration data
    skills: list[Skill]
    hooks: list[Hook]
    commands: list[Command]
    agents: list[Agent]
    mcp_servers: list[MCPServer]

    # UI state
    spawn_mode: str  # "external" or "embedded"
    show_active_only: bool

    # Lifecycle management
    _spawned_pids: list[int]
    _on_session_update: list[Callable[[], None]]
```

**Key Methods**:
- `select_session()`, `select_tool()`: Update selection state
- `load_session()`, `update_session()`: Load/refresh session data from JSONL
- `load_configs()`: Discover skills, hooks, commands, agents, and MCP servers
- `toggle_spawn_mode()`: Switch between embedded/external terminal modes
- `toggle_active_filter()`: Toggle between showing all/active sessions
- `add_update_listener()`, `notify_update()`: Observer pattern for UI updates
- `track_spawned_pid()`, `cleanup_spawned_processes()`: Process lifecycle management

### ClaudeProcess Class

Represents a running Claude process with metadata:

```python
@dataclass
class ClaudeProcess:
    pid: int                    # Process ID
    cwd: str                    # Working directory
    command: str                # Full command line
    session_id: str | None      # Associated session ID (if detected)
```

### Active Session Detection

The module uses multiple strategies to detect active sessions:

1. **File Modification Time**: Sessions modified in last 30 seconds are considered active
2. **Process Matching**: Finds Claude processes and matches to session paths via working directory
3. **History File**: Reads `~/.claude/history.jsonl` to map projects to current session IDs
4. **Directory Comparison**: Exact path matching between session project paths and process CWDs

## Submodules

The root module coordinates with several submodules:

- **`discovery/`**: Session file discovery and JSONL parsing
  - `watcher.py`: File system watching for real-time updates
  - `parser.py`: JSONL parsing and session data extraction
  - `config_parser.py`: Configuration file parsing (skills, hooks, agents, MCP servers)

- **`spawner/`**: New session spawning functionality
  - `terminal.py`: Terminal emulator integration for spawning Claude

- **`store/`**: Data models and storage
  - `models.py`: Core data models (Session, ToolUse, ConversationMessage)
  - `config_models.py`: Configuration models (Skill, Hook, Command, Agent, MCPServer)

- **`tui/`**: Terminal UI implementation
  - `app.py`: Main Textual application
  - `screens/`: Different UI screens
  - `widgets/`: Reusable UI components

## Dependencies

### Internal Dependencies
- `discovery.parser`: For parsing session JSONL files
- `discovery.config_parser`: For discovering Claude configurations
- `store.models`: Data models for sessions and tool uses
- `store.config_models`: Data models for configurations
- `tui.app`: Main TUI application class

### External Dependencies
- **Python 3.10+**: Required for modern type hints and language features
- **Textual**: Terminal UI framework (imported in `tui.app`)
- **Rich**: Text formatting and syntax highlighting
- **watchdog**: File system monitoring
- **subprocess**: Process management and discovery
- **json**: JSONL parsing

### System Dependencies
- `ps`: Process listing (Unix/macOS)
- `lsof`: Process working directory detection (macOS)
- `pgrep`: Process search (Unix/macOS)

## Usage Examples

### Programmatic Usage

```python
from pathlib import Path
from claude_agent_tui.state import AppState

# Create application state
state = AppState()

# Load configurations
state.load_configs()

# Load a session
session_path = Path.home() / ".claude" / "projects" / "myproject" / "session.jsonl"
session = state.load_session(session_path)

# Access session data
print(f"Session: {session.session_id}")
print(f"Tools used: {len(session.tool_uses)}")
for tool in session.tool_uses:
    print(f"  - {tool.tool_name}: {tool.preview}")
```

### Process Management

```python
from claude_agent_tui.process import find_claude_processes, kill_session

# Find all running Claude processes
processes = find_claude_processes()
for proc in processes:
    print(f"PID {proc.pid}: {proc.command} (in {proc.cwd})")

# Kill a specific session
success, message = kill_session("session-abc123")
print(message)
```

### CLI Usage

```bash
# Standard launch (uses ~/.claude/projects)
claude-tui

# Demo mode with sample data
claude-tui --demo

# Custom sessions directory
claude-tui -d /path/to/sessions

# Check version
claude-tui --version
```

## Data Flow

1. **Startup**:
   - `__main__.main()` parses CLI arguments
   - Creates `AppState` instance
   - Launches `ClaudeAgentVizApp` (from `tui.app`)

2. **Session Discovery**:
   - `discovery.watcher` monitors `~/.claude/projects` for changes
   - JSONL files are parsed by `discovery.parser`
   - Converted to `Session` models via `state.convert_parsed_session()`
   - Stored in `AppState.sessions`

3. **Active Detection**:
   - `state.get_active_claude_processes()` finds running processes
   - Session `is_active` flag set based on directory matching
   - History file parsed to find current session IDs

4. **UI Interaction**:
   - User selects session → `AppState.select_session()`
   - State notifies listeners → UI widgets update
   - Tool details displayed in detail panel

5. **Process Spawning**:
   - User triggers new session → `spawner.terminal` creates process
   - PID tracked in `AppState._spawned_pids`
   - On exit, `AppState.cleanup_spawned_processes()` terminates orphaned processes

## Configuration Management

The module discovers and manages Claude Code configurations:

- **Skills**: Custom commands and workflows (from `~/.claude/skills/`)
- **Hooks**: Lifecycle event handlers (from `claude.yaml`)
- **Commands**: Slash commands (from `claude.yaml`)
- **Agents**: Agent definitions (from `claude.yaml` or plugins)
- **MCP Servers**: Model Context Protocol servers (from `claude.yaml`)

Configuration items are loaded via `AppState.load_configs()` and can be inspected in the UI.

## Error Handling

The module includes robust error handling:
- **Missing Dependencies**: Graceful error messages with installation instructions
- **Permission Errors**: Handled when accessing process information
- **Invalid JSONL**: Skipped with warnings during parsing
- **Process Not Found**: Returns empty lists rather than crashing
- **File System Errors**: Caught and logged without stopping the application

## Cleanup and Lifecycle

The application manages process lifecycle carefully:

1. **Process Tracking**: All spawned Claude processes are tracked in `AppState._spawned_pids`
2. **Normal Exit**: Processes are cleaned up via `cleanup_spawned_processes()`
3. **Forced Exit**: SIGTERM sent to all tracked processes
4. **Orphan Prevention**: Ensures no Claude processes remain after exit

## Platform Considerations

- **macOS**: Primary platform, uses `lsof` for process directory detection
- **Linux**: Supported with fallback to `/proc/{pid}/cwd`
- **Windows**: Limited support (process management may not work)

## Future Extensibility

The module is designed for extensibility:
- **Observer Pattern**: State changes notify UI components
- **Plugin System**: Configuration discovery supports plugins
- **Multiple Spawn Modes**: Embedded and external terminal support
- **Configurable Paths**: Custom session directories supported
- **Demo Mode**: Testing without real data

## See Also

- **Store Models** (`store/CLAUDE.md`): Data model documentation
- **TUI Application** (`tui/CLAUDE.md`): UI component documentation
- **Discovery System** (`discovery/CLAUDE.md`): Session parsing details
- **Main README**: User-facing documentation and keybindings
