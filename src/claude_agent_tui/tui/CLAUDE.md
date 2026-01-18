# TUI Module

## Overview

The `tui` module is the Terminal User Interface (TUI) component of Claude Agent Visualizer. It provides an interactive, real-time terminal application for visualizing and managing Claude Code agent sessions. Built on the Textual framework, this module orchestrates the entire user interface, session monitoring, and user interactions.

## What This Module Does

The TUI module serves as the primary interface for:

1. **Session Visualization**: Displays all Claude sessions from `~/.claude/projects` with real-time updates
2. **Active Session Detection**: Automatically identifies and highlights running Claude processes using PID matching
3. **Tool Inspection**: Shows detailed information about every tool use (Read, Write, Edit, Bash, etc.) with full input/output
4. **Session Management**: Spawns new sessions, resumes existing ones, and terminates running processes
5. **Configuration Browsing**: Views Claude configuration including skills, hooks, commands, agents, and MCP servers
6. **Live File Watching**: Monitors session files for changes and updates the UI in real-time

## Key Files

### `__init__.py`
Simple module initialization that exports the main application class:
- Exports: `ClaudeAgentVizApp`
- Purpose: Provides clean API for importing the TUI application

### `app.py`
The core application file containing the `ClaudeAgentVizApp` class. This is the main orchestrator that:
- Defines the application layout using Textual's compose pattern
- Manages application state through `AppState`
- Handles user input via keybindings and actions
- Coordinates communication between widgets
- Manages file watching for real-time session updates
- Handles process spawning and cleanup

## Important Classes and Concepts

### `ClaudeAgentVizApp`

The main Textual application class that extends `textual.app.App`.

**Constructor Parameters:**
- `sessions_dir: Path | None` - Directory containing session JSONL files (defaults to `~/.claude/projects`)
- `demo_mode: bool` - Whether to run with sample data instead of real sessions
- `**kwargs` - Additional Textual App parameters

**Key Attributes:**
- `state: AppState` - Central application state manager
- `_watcher: SessionWatcher | None` - File system watcher for session changes

**Layout Structure:**
```
Header
└── Main Layout (Vertical)
    ├── Content Area (Horizontal)
    │   ├── Sidebar (Tabbed)
    │   │   ├── Sessions Tab
    │   │   │   ├── SessionList widget
    │   │   │   └── ToolList widget
    │   │   └── Config Tab
    │   │       ├── SkillList widget
    │   │       ├── HookList widget
    │   │       ├── CommandList widget
    │   │       ├── AgentList widget
    │   │       └── MCPServerList widget
    │   └── Main Content
    │       └── DetailPanel widget
    └── Status Indicator
Footer
```

**Key Actions (Keybindings):**
- `q` - Quit application
- `n` - New session (spawns new Claude session)
- `c` - Resume session (continue existing session)
- `k` - Kill session (terminate running process)
- `r` - Refresh (reload sessions from disk)
- `ESC` - Back navigation (tool → session → config → base state)
- `?` - Help (show keybindings and info)

### State Management

The app uses `AppState` from `../state` to manage:
- Session list and selection
- Tool list and selection
- Configuration items (skills, hooks, commands, agents, MCP servers)
- Selection state tracking
- Update listeners for reactive UI updates

### Active Session Detection

The app implements sophisticated active session detection:
1. Uses `get_active_claude_processes()` to find running Claude PIDs
2. Matches PIDs to session files by resolving project paths
3. Marks the N most recently modified sessions as active (where N = number of PIDs per directory)
4. Associates each active session with its corresponding PID

### File Watching

When not in demo mode, the app uses `SessionWatcher` to monitor session files:
- Watches for file modifications and new file creation
- Calls `_on_session_file_changed()` for updates to existing sessions
- Calls `_on_session_file_created()` for new sessions
- Uses `call_from_thread()` to safely update UI from watcher thread
- Automatically skips subagent files to avoid noise

### Process Management

The app manages subprocess lifecycle:
- Spawns new Claude sessions via `spawn_session()`
- Resumes sessions via `spawn_resume_session()`
- Kills sessions by session ID or PID
- Cleans up spawned processes on unmount to prevent orphans

## How to Use This Module

### Basic Usage

```python
from claude_agent_tui.tui import ClaudeAgentVizApp

# Run with default sessions directory (~/.claude/projects)
app = ClaudeAgentVizApp()
app.run()

# Run with custom sessions directory
app = ClaudeAgentVizApp(sessions_dir=Path("/path/to/sessions"))
app.run()

# Run in demo mode with sample data
app = ClaudeAgentVizApp(demo_mode=True)
app.run()
```

### Command Line Interface

The module is typically invoked via the CLI entry point:

```bash
# Default: real sessions from ~/.claude/projects
claude-tui

# Demo mode with sample data
claude-tui --demo

# Custom sessions directory
claude-tui -d /path/to/sessions
```

### Key User Workflows

**1. Browsing Sessions:**
- Sessions appear in the left sidebar
- Green indicator shows active (running) sessions
- Select a session to view details in the main panel

**2. Inspecting Tools:**
- Select a session to populate the Tools list
- Click a tool to see full input/output details
- Supports all tool types: Read, Write, Edit, Bash, Grep, etc.

**3. Managing Sessions:**
- Press `n` to spawn a new Claude session
- Press `c` to resume the selected session
- Press `k` to kill the selected session
- Press `r` to refresh the session list

**4. Viewing Configuration:**
- Switch to the "Config" tab to browse Claude configuration
- View skills, hooks, commands, agents, and MCP servers
- Select any config item to see details in the main panel

**5. Navigation:**
- Use arrow keys or mouse to select items
- Press `ESC` to navigate back through views
- Press `?` for help at any time

## Dependencies and Relationships

### External Dependencies

**Textual Framework:**
- `textual.app.App` - Base application class
- `textual.widgets.*` - UI widget components
- `textual.containers.*` - Layout containers
- `textual.binding.Binding` - Keybinding definitions

**Rich Library:**
- Used by Textual for rendering
- Required for syntax highlighting and formatting

**Watchdog (Optional):**
- Used for file system monitoring
- Gracefully degrades if not installed

### Internal Module Dependencies

**State Management:**
- `../state.AppState` - Central state manager
- `../state.get_active_claude_directories()` - Process detection
- `../state.get_active_claude_processes()` - PID retrieval

**Data Models:**
- `../store.config_models` - Skill, Hook, Command, Agent, MCPServer

**Discovery:**
- `../discovery.parser.parse_sessions_in_directory()` - Session parsing
- `../discovery.watcher.SessionWatcher` - File watching

**Process Management:**
- `../spawner.terminal.spawn_session()` - New session spawning
- `../spawner.terminal.spawn_resume_session()` - Session resumption
- `../process.kill_session()` - Session termination

**Demo Data:**
- `../demo.create_demo_sessions()` - Sample data generation

### Submodules

**Widgets (`./widgets/`):**
- `SessionList` - Lists all sessions with active indicators
- `ToolList` - Lists tool uses for selected session
- `DetailPanel` - Main content area showing detailed information
- `ConfigList` - Base class for config item lists
- `SkillList`, `HookList`, `CommandList`, `AgentList`, `MCPServerList` - Specific config lists
- `ClaudeTerminal`, `ResumeTerminal` - Embedded terminal widgets
- `ContentViewer` - Content display component

**Screens (`./screens/`):**
- `NewSessionScreen` - Dialog for creating new sessions
- `TerminalScreen` - Full-screen terminal view
- `EmbeddedTerminalScreen` - Embedded terminal in main view
- `ResumeTerminalScreen` - Terminal for resuming sessions

## Architecture Notes

### Event Flow

1. **User Interaction** → Widget emits custom message
2. **App Handler** → Processes message, updates state
3. **State Update** → Triggers registered listeners
4. **UI Update** → Widgets refresh to reflect new state

### Update Pattern

The app uses a consistent update pattern:
- `_update_session_list()` - Refreshes session widget
- `_update_tool_list()` - Refreshes tool widget
- `_update_detail_panel()` - Refreshes detail view
- `_update_config_lists()` - Refreshes all config widgets
- `_update_status()` - Refreshes status bar

### Threading Model

- Main UI runs on Textual's event loop
- File watcher runs on separate thread
- `call_from_thread()` used to bridge watcher → UI updates
- Process spawning uses subprocess but doesn't block UI

### CSS Styling

The app includes extensive CSS-in-Python for layout and theming:
- Sidebar width: 35 columns
- Sessions panel: 40% of sidebar height
- Tools panel: 60% of sidebar height
- Main content: Flexible width (1fr)
- Responsive to terminal size changes

## Future Extensions

This module is designed to be extensible:
- Add new widget types by creating classes in `widgets/`
- Add new screens by creating classes in `screens/`
- Extend actions by adding methods with `action_` prefix
- Add keybindings via the `BINDINGS` class attribute
- Customize layout by modifying `compose()` method
- Add state fields by extending `AppState`

## Testing

The module supports both real and demo modes:
- **Demo Mode**: Use `demo_mode=True` for testing without real sessions
- **Real Mode**: Use actual session files from `~/.claude/projects`
- **Custom Path**: Specify `sessions_dir` for testing with specific data

## Performance Considerations

- File watching is optional and degrades gracefully
- Sessions are parsed incrementally, not all at once
- Only selected sessions have their tools loaded in detail
- Subagent files are explicitly skipped to reduce noise
- Process cleanup on unmount prevents resource leaks
