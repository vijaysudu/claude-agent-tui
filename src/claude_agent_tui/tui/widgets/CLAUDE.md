# TUI Widgets Module

## Overview

The `widgets` module contains the core UI components for the Claude Agent Visualizer Terminal User Interface (TUI). These widgets are built using the Textual framework and provide interactive displays for Claude sessions, tool executions, configuration items, and embedded terminal functionality.

## Module Purpose

This module provides specialized Textual widgets that:
- Display Claude agent sessions and their conversation history
- Visualize tool executions with syntax highlighting
- Show configuration items (skills, hooks, commands, agents, MCP servers)
- Provide embedded terminal functionality for creating and resuming Claude sessions
- Render detailed information panels with rich formatting

## Key Files and Components

### List Widgets

#### `session_list.py` - SessionList
**Purpose**: Displays a list of Claude sessions with status and metadata.

**Key Features**:
- Shows active/inactive session status with green indicator
- Displays project name, summary, tool count, and relative timestamps
- Formats relative time (e.g., "2h ago", "5m ago")
- Emits `SessionSelected` message on selection

**Usage**:
```python
session_list = SessionList()
session_list.set_sessions(sessions)  # List[Session]
```

#### `tool_list.py` - ToolList
**Purpose**: Lists all tool uses within a selected session.

**Key Features**:
- Status icons (✓ completed, ✗ error, ⏳ pending, ⏵ running)
- Tool-specific icons (Read, Edit, Write, Bash, Grep, etc.)
- Truncated preview of tool operations
- Emits `ToolSelected` message on selection

**Tool Icons**:
- Read:
- Edit:
- Write:
- Bash:
- Grep:
- Glob:
- Task:
- WebFetch:
- AskUserQuestion:

#### `config_list.py` - ConfigList (Base Class)
**Purpose**: Generic base widget for displaying collapsible configuration item lists.

**Key Features**:
- Generic implementation using Python generics `Generic[T]`
- Collapsible container with count in header
- Emits `ItemSelected` message with item type and ID
- Methods: `set_items()`, `expand_list()`, `collapse_list()`

**Subclasses**:
- `AgentList` - Displays Claude agents with color and model info
- `SkillList` - Shows skills with plugin indicators
- `HookList` - Lists hooks by type (UserPromptSubmit, PreToolUse, etc.)
- `CommandList` - Shows custom commands with `/` prefix
- `MCPServerList` - Displays MCP server configurations

### Detail Panels

#### `detail_panel.py` - DetailPanel
**Purpose**: Main detail view that adapts to show different content types.

**Supported Views**:
1. **Session View**: Full conversation display with user/assistant messages
   - Shows thinking content (collapsible)
   - Displays tool uses inline with results
   - Compact tool representation with status icons
   - Input field for resuming sessions

2. **Tool View**: Detailed tool execution information
   - Syntax-highlighted file contents (Read, Write)
   - Diff visualization (Edit)
   - Command output with bash syntax (Bash)
   - Search results (Grep, Glob)
   - Parameters display in JSON format

3. **Config Item Views**:
   - Skill details with markdown content
   - Hook configuration with bash commands
   - Command details with markdown
   - Agent configuration with tools and model info
   - MCP server details with environment variables (masked sensitive values)

4. **Welcome View**: Keyboard shortcuts and help

**Message Types**:
- `ReplySubmitted`: Sent when user enters text to resume a session

**Methods**:
- `show_session(session)`: Display session conversation
- `show_tool(tool)`: Display tool details
- `show_skill(skill)`: Display skill configuration
- `show_hook(hook)`: Display hook configuration
- `show_command(command)`: Display command configuration
- `show_agent(agent)`: Display agent configuration
- `show_mcp_server(server)`: Display MCP server configuration
- `show_welcome()`: Display welcome/help screen

#### `content_viewer.py` - ContentViewer
**Purpose**: Specialized widget for displaying tool results with syntax highlighting.

**Supported Content Types**:
- File contents with language detection (Python, JavaScript, JSON, YAML, etc.)
- Diff visualization (Edit operations)
- Command output (Bash)
- Search results (Grep, Glob)
- Error messages
- Generic content with titles

**Methods**:
- `show_file_content(content, file_path)`: Display file with syntax highlighting
- `show_diff(old_string, new_string, file_path)`: Show before/after changes
- `show_command_output(command, output, is_error)`: Display command results
- `show_search_results(pattern, results, search_type)`: Show search matches
- `show_generic_content(title, content)`: Display generic content
- `show_error(error_message)`: Display error message
- `clear()`: Clear the viewer

**Language Detection**:
Supports 20+ languages including Python, JavaScript, TypeScript, JSON, YAML, Markdown, Bash, Rust, Go, and more.

### Terminal Widgets

#### `claude_terminal.py` - ClaudeTerminal
**Purpose**: Embedded PTY-based terminal for starting new Claude sessions.

**Key Features**:
- Full PTY (pseudo-terminal) implementation using `pty.openpty()`
- Forks a process to run the `claude` command
- Real-time output streaming from Claude
- Input submission for interactive chat
- Session lifecycle management (start, stop, graceful/force shutdown)
- Terminal size control via `TIOCSWINSZ` ioctl

**Message Types**:
- `SessionStarted(pid)`: Sent when session starts
- `SessionEnded(exit_code)`: Sent when session ends
- `OutputReceived(output)`: Sent when output is received

**Methods**:
- `spawn_claude()`: Start a new Claude session (threaded)
- `send_input(text)`: Send user input to Claude
- `stop_session()`: Stop the session
- `send_interrupt()`: Send Ctrl+C
- `graceful_shutdown()`: Send `/exit` command
- `force_shutdown()`: Double Ctrl+C then SIGTERM
- `set_terminal_size(rows, cols)`: Update terminal dimensions

**Properties**:
- `is_running`: Check if session is active
- `pid`: Get process ID

#### `resume_terminal.py` - ResumeTerminal
**Purpose**: Embedded terminal for resuming existing Claude sessions.

**Key Differences from ClaudeTerminal**:
- Uses `claude --resume <session_id>` command
- Accepts optional `initial_message` parameter
- Automatically sends initial message after 1.5s delay
- Tracks `_initial_message_sent` flag

**Constructor Parameters**:
```python
ResumeTerminal(
    session_id: str,          # Required: session to resume
    cwd: str | None = None,   # Working directory
    initial_message: str | None = None  # Auto-send message
)
```

## Widget Hierarchy and Relationships

```
Container (Textual base)
├── DetailPanel - Main detail view (adapts to content type)
├── ContentViewer - Syntax-highlighted content display
├── ClaudeTerminal - New session terminal
└── ResumeTerminal - Resume session terminal

OptionList (Textual base)
├── SessionList - Session list
└── ToolList - Tool execution list

Container + Generic[T]
└── ConfigList - Base for config lists
    ├── AgentList - Agent configurations
    ├── SkillList - Skill configurations
    ├── HookList - Hook configurations
    ├── CommandList - Custom commands
    └── MCPServerList - MCP server configs
```

## Dependencies

### Internal Dependencies
- `...store.models`: Session, ToolUse, ToolStatus, ConversationMessage, MessageRole
- `...store.config_models`: Skill, Hook, Command, Agent, MCPServer

### External Dependencies
- `textual`: TUI framework (Container, OptionList, RichLog, Input, etc.)
- `rich`: Text formatting and syntax highlighting (Text, Syntax)
- Standard library: `pty`, `os`, `signal`, `termios`, `fcntl`, `struct`, `json`, `pathlib`

## Usage Patterns

### 1. Displaying Sessions
```python
# In a screen or app
session_list = SessionList()
session_list.set_sessions(sessions)

# Handle selection
def on_session_list_session_selected(self, message: SessionList.SessionSelected) -> None:
    session_id = message.session_id
    # Load and display session details
```

### 2. Showing Tool Details
```python
tool_list = ToolList()
tool_list.set_tools(session.tool_uses)

detail_panel = DetailPanel()
detail_panel.show_tool(tool)  # Show specific tool
```

### 3. Displaying Configuration
```python
skill_list = SkillList()
skill_list.set_items(skills)

# When skill selected
detail_panel.show_skill(selected_skill)
```

### 4. Creating a New Session
```python
terminal = ClaudeTerminal(cwd="/path/to/project")

# Handle session lifecycle
def on_claude_terminal_session_started(self, message: ClaudeTerminal.SessionStarted) -> None:
    self.log(f"Session started with PID {message.pid}")

def on_claude_terminal_session_ended(self, message: ClaudeTerminal.SessionEnded) -> None:
    self.log(f"Session ended with code {message.exit_code}")
```

### 5. Resuming a Session
```python
terminal = ResumeTerminal(
    session_id="abc123",
    cwd="/path/to/project",
    initial_message="Continue the analysis"
)
```

## Styling and CSS

All widgets include `DEFAULT_CSS` class attributes that define:
- Layout (vertical, grid, etc.)
- Borders and colors using Textual CSS variables
- Focus states (`:focus`)
- Hover states (`:hover`)
- Scroll behavior (`scrollbar-gutter: stable`)

**Common CSS Variables**:
- `$primary`: Primary border color
- `$accent`: Accent/highlight color
- `$surface`: Background color
- `$text`: Text color
- `$text-muted`: Dimmed text
- `$error`: Error color
- `$success`: Success/green color

## Message Protocol

Widgets communicate using Textual's message system:

1. **SessionList.SessionSelected**: User selected a session
2. **ToolList.ToolSelected**: User selected a tool
3. **ConfigList.ItemSelected**: User selected a config item (skill, hook, etc.)
4. **DetailPanel.ReplySubmitted**: User submitted text to resume session
5. **ClaudeTerminal.SessionStarted**: Terminal session started
6. **ClaudeTerminal.SessionEnded**: Terminal session ended
7. **ClaudeTerminal.OutputReceived**: Terminal output received

## Special Features

### 1. Color Support in AgentList
The `AgentList` widget supports agent colors with validation:
- Valid Rich colors: red, green, blue, cyan, magenta, yellow, white, black, bright variants
- Color mapping: orange→bright_red, purple→magenta, pink→bright_magenta, etc.
- Function: `get_valid_color(color)` converts to valid Rich color names

### 2. Syntax Highlighting
The `get_language_from_path()` function detects file types:
- Supports 20+ programming languages
- Special handling for Dockerfile (no extension)
- Falls back to "text" for unknown types
- Uses Rich's Syntax widget with "monokai" theme

### 3. Conversation Rendering
The `DetailPanel` renders conversations in a structured format:
- User messages: Blue box with `╭─ User ─...`
- Assistant messages: Green box with `╭─ Claude ─...`
- Thinking content: Collapsed with 💭 emoji
- Tool uses: Inline compact representation with status

### 4. PTY Terminal Management
Both terminal widgets use PTY for full terminal emulation:
- Fork-exec pattern for subprocess management
- Thread-safe output writing using `app.call_from_thread()`
- Graceful shutdown sequence: `/exit` → Ctrl+C → Ctrl+C → SIGTERM
- Signal handling: SIGTERM for cleanup

### 5. Sensitive Data Masking
The `DetailPanel.show_mcp_server()` method masks sensitive environment variables:
- Detects keys containing: "key", "token", "secret", "password"
- Shows: `***` + last 4 characters
- Example: `API_KEY=***xyz9`

## Error Handling

Widgets implement defensive error handling:
- Graceful fallbacks for syntax highlighting failures
- Try-except blocks around timestamp parsing
- OSError handling in PTY operations
- Null checks before widget queries
- Default values for missing data

## Testing Considerations

When testing widgets:
1. Mock the store models (Session, ToolUse, etc.)
2. Use Textual's test utilities for async operations
3. Test message emission and handling
4. Verify CSS rendering in different terminal sizes
5. Test PTY widgets with mock file descriptors

## Architecture Notes

1. **Separation of Concerns**: List widgets display, detail panels render, terminal widgets execute
2. **Message-Driven**: Loose coupling via Textual messages
3. **Generic Base Classes**: ConfigList reduces duplication for similar widgets
4. **Rich Integration**: Heavy use of Rich for formatting and syntax highlighting
5. **Thread Safety**: PTY operations use proper thread synchronization
6. **Responsive Design**: CSS-based layout adapts to terminal size
