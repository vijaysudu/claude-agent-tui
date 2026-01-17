# Architecture

## System Overview

Claude Agent Visualizer consists of four main components that work together to provide real-time agent monitoring:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              User's Machine                                      │
│                                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                     │
│  │ Claude Session │  │ Claude Session │  │ Claude Session │                     │
│  │   Terminal 1   │  │   Terminal 2   │  │   Terminal 3   │                     │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                     │
│          │                   │                   │                               │
│          │ Hooks emit events │                   │                               │
│          └───────────────────┼───────────────────┘                               │
│                              ▼                                                   │
│                 ┌────────────────────────┐                                       │
│                 │     Event Emitter      │                                       │
│                 │   (claude-viz-emit)    │                                       │
│                 └───────────┬────────────┘                                       │
│                             │                                                    │
│                             ▼                                                    │
│                 ┌────────────────────────┐                                       │
│                 │     Event Store        │                                       │
│                 │      (SQLite)          │                                       │
│                 │ ~/.local/share/claude- │                                       │
│                 │   agent-viz/events.db  │                                       │
│                 └───────────┬────────────┘                                       │
│                             │                                                    │
│            ┌────────────────┼────────────────┐                                   │
│            │                │                │                                   │
│            ▼                ▼                ▼                                   │
│  ┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐                        │
│  │  File Watcher   │ │  DB Reader  │ │  Input Bridge   │                        │
│  │ (watchfiles)    │ │             │ │                 │                        │
│  └────────┬────────┘ └──────┬──────┘ └────────┬────────┘                        │
│           │                 │                 │                                  │
│           └─────────────────┼─────────────────┘                                  │
│                             ▼                                                    │
│                 ┌────────────────────────┐                                       │
│                 │    Textual TUI App     │                                       │
│                 │                        │                                       │
│                 │  ┌──────────────────┐  │                                       │
│                 │  │   Session Tree   │  │                                       │
│                 │  │    Component     │  │                                       │
│                 │  └──────────────────┘  │                                       │
│                 │  ┌──────────────────┐  │                                       │
│                 │  │  Agent Details   │  │                                       │
│                 │  │     Panel        │  │                                       │
│                 │  └──────────────────┘  │                                       │
│                 │  ┌──────────────────┐  │                                       │
│                 │  │   Input Modal    │  │                                       │
│                 │  │                  │  │                                       │
│                 │  └──────────────────┘  │                                       │
│                 └────────────────────────┘                                       │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Event Emitter (`claude-viz-emit`)

A lightweight CLI script that Claude Code hooks call to emit events.

**Location:** `src/claude_agent_viz/collector/emitter.py`

**Responsibilities:**
- Receive event data from hooks via command-line arguments or stdin
- Validate event schema
- Write events to SQLite database
- Must be fast (<50ms) to not slow down Claude Code

**Hook Integration:**

```json
// ~/.claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "commands": ["claude-viz-emit agent-start"]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Task",
        "commands": ["claude-viz-emit agent-complete"]
      },
      {
        "matcher": "*",
        "commands": ["claude-viz-emit tool-use"]
      }
    ]
  }
}
```

**Event Flow:**

```
Claude Code                    Event Emitter                  SQLite
    │                              │                            │
    │  PreToolUse: Task            │                            │
    │─────────────────────────────▶│                            │
    │  (stdin: event JSON)         │                            │
    │                              │  INSERT INTO events        │
    │                              │───────────────────────────▶│
    │                              │                            │
    │◀─────────────────────────────│                            │
    │  exit 0                      │                            │
```

---

### 2. Event Store (SQLite)

Persistent storage for agent events with efficient querying.

**Location:** `~/.local/share/claude-agent-viz/events.db`

**Schema:**

```sql
-- Sessions table
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,           -- Unique session ID (from Claude)
    working_dir TEXT NOT NULL,     -- Directory where Claude was started
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    status TEXT DEFAULT 'active',  -- active, completed, failed
    pid INTEGER                    -- Process ID of Claude session
);

-- Agents table (hierarchical)
CREATE TABLE agents (
    id TEXT PRIMARY KEY,           -- Unique agent ID
    session_id TEXT NOT NULL,      -- FK to sessions
    parent_id TEXT,                -- FK to parent agent (NULL for root)
    agent_type TEXT NOT NULL,      -- Explore, Plan, Bash, general-purpose, etc.
    description TEXT,              -- Short description of task
    status TEXT DEFAULT 'running', -- running, completed, failed, waiting_input
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    tokens_used INTEGER DEFAULT 0,
    messages_count INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (parent_id) REFERENCES agents(id)
);

-- Tool uses table
CREATE TABLE tool_uses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,        -- FK to agents
    tool_name TEXT NOT NULL,       -- Read, Write, Bash, Skill, MCP, etc.
    tool_category TEXT,            -- command, skill, mcp, builtin
    parameters TEXT,               -- JSON of tool parameters
    result_preview TEXT,           -- First 200 chars of result
    status TEXT DEFAULT 'running', -- running, completed, failed
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    duration_ms INTEGER,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Input requests table
CREATE TABLE input_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,        -- FK to agents
    session_id TEXT NOT NULL,      -- FK to sessions
    request_type TEXT NOT NULL,    -- question, confirmation, selection
    prompt TEXT NOT NULL,          -- The question/prompt shown to user
    options TEXT,                  -- JSON array of options (if selection)
    response TEXT,                 -- User's response (when provided)
    status TEXT DEFAULT 'pending', -- pending, responded, expired
    created_at DATETIME NOT NULL,
    responded_at DATETIME,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Indexes for efficient queries
CREATE INDEX idx_agents_session ON agents(session_id);
CREATE INDEX idx_agents_parent ON agents(parent_id);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_tool_uses_agent ON tool_uses(agent_id);
CREATE INDEX idx_input_requests_pending ON input_requests(status) WHERE status = 'pending';
```

---

### 3. TUI Application (Textual)

The main dashboard application built with Textual.

**Location:** `src/claude_agent_viz/tui/app.py`

**Component Hierarchy:**

```
App (ClaudeAgentVizApp)
├── Header
│   └── StatusBar (sessions count, agents count, pending inputs)
├── Container (main area)
│   ├── SessionTree (left panel, 40%)
│   │   └── Tree widget with session/agent nodes
│   └── DetailPanel (right panel, 60%)
│       ├── AgentInfo (selected agent details)
│       ├── ToolList (tools used by agent)
│       └── ContextMetrics (tokens, messages)
├── Footer
│   └── KeyBindings display
└── InputModal (overlay, shown when responding)
    ├── PromptDisplay
    ├── OptionsSelector (if applicable)
    └── TextInput / Buttons
```

**Key Classes:**

```python
# Main application
class ClaudeAgentVizApp(App):
    """Main Textual application."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("space", "toggle_expand", "Expand/Collapse"),
        ("tab", "next_session", "Next Session"),
        ("enter", "respond", "Respond to Input"),
        ("r", "refresh", "Refresh"),
        ("?", "help", "Help"),
    ]

# Session tree widget
class SessionTree(Tree):
    """Hierarchical tree of sessions and agents."""

    def on_mount(self):
        self.root.expand()
        self.watch_for_updates()

# Agent detail panel
class AgentDetailPanel(Container):
    """Shows details for selected agent."""

    def update_agent(self, agent: Agent):
        """Update panel with new agent data."""
        pass

# Input modal
class InputModal(ModalScreen):
    """Modal for responding to input requests."""

    def __init__(self, request: InputRequest):
        self.request = request
        super().__init__()
```

---

### 4. Input Bridge

Mechanism for sending user responses back to waiting Claude sessions.

**Approach:** File-based signaling with polling

**How it works:**

1. User selects an agent with pending input in the dashboard
2. User types response and presses Enter
3. Dashboard writes response to a known file location
4. Claude Code hook polls for response file and reads it
5. Response is injected into the session

**File Protocol:**

```
~/.local/share/claude-agent-viz/responses/
├── <session-id>-<request-id>.response   # Response content
└── <session-id>-<request-id>.ready      # Signal file (empty)
```

**Response Flow:**

```
Dashboard                     Response Files                Claude Hook
    │                              │                            │
    │  User enters response        │                            │
    │──────────────────────────────▶                            │
    │  Write: abc123-1.response    │                            │
    │  Write: abc123-1.ready       │                            │
    │                              │                            │
    │                              │◀───────────────────────────│
    │                              │  Poll for .ready file      │
    │                              │                            │
    │                              │  Read .response            │
    │                              │───────────────────────────▶│
    │                              │                            │
    │                              │  Delete files              │
    │                              │◀───────────────────────────│
```

**Alternative Approach (Future):** Unix domain sockets for lower latency, similar to claude-canvas IPC.

---

## Data Flow

### Event Lifecycle

```
1. User starts Claude Code
   └─▶ Session created in DB (status: active)

2. Claude spawns an agent (Task tool)
   └─▶ PreToolUse hook fires
       └─▶ claude-viz-emit agent-start
           └─▶ Agent row created (status: running)

3. Agent uses a tool (e.g., Grep)
   └─▶ PostToolUse hook fires
       └─▶ claude-viz-emit tool-use
           └─▶ Tool use row created

4. Agent needs user input (AskUserQuestion)
   └─▶ Hook fires with input request data
       └─▶ Input request row created (status: pending)
       └─▶ Agent status updated to waiting_input

5. User responds via dashboard
   └─▶ Response written to file
   └─▶ Input request updated (status: responded)
   └─▶ Agent status updated to running

6. Agent completes
   └─▶ PostToolUse hook fires
       └─▶ claude-viz-emit agent-complete
           └─▶ Agent row updated (status: completed)

7. User closes Claude Code
   └─▶ Session cleanup hook fires
       └─▶ Session updated (status: completed)
```

---

## Threading Model

The TUI runs on the main thread with async workers for:

1. **Database Watcher** - Polls SQLite for changes every 100ms
2. **File Watcher** - Watches for new response acknowledgments
3. **UI Renderer** - Textual's built-in compositor

```python
class ClaudeAgentVizApp(App):

    @work(exclusive=True)
    async def watch_database(self):
        """Background worker to poll for DB changes."""
        while True:
            await self.refresh_sessions()
            await asyncio.sleep(0.1)  # 100ms

    @work(exclusive=True)
    async def watch_responses(self):
        """Background worker to watch for response acks."""
        async for changes in awatch(RESPONSES_DIR):
            await self.handle_response_ack(changes)
```

---

## Security Considerations

1. **Local-only**: All data stays on the user's machine
2. **No network**: No external connections required
3. **File permissions**: Event DB and response files use restrictive permissions (600)
4. **Input sanitization**: Response content is sanitized before writing
5. **No secrets in events**: Tool parameters are sanitized to remove sensitive data

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Hook execution time | < 50ms |
| UI refresh rate | 10 fps (100ms) |
| Database query time | < 10ms |
| Memory usage (idle) | < 50MB |
| Memory usage (100 agents) | < 100MB |
| Startup time | < 500ms |

---

## Extension Points

### Custom Tool Categorization

```python
# config.toml
[tools.categories]
"mcp__github__*" = "github"
"mcp__datadog__*" = "datadog"
"Skill:*" = "skills"
```

### Custom Status Colors

```python
# config.toml
[colors.custom]
github = "#6e5494"
datadog = "#632ca6"
```

### Webhook Notifications (Future)

```python
# config.toml
[notifications.webhook]
url = "https://hooks.slack.com/..."
events = ["input_request", "session_complete"]
```
