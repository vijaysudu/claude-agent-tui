# Plan Improvements - Iteration 1

## Key Findings from Hook Research

### Available Data
- `CLAUDE_CODE_SESSION_ID` - Session identifier (use this, don't generate our own)
- `CLAUDE_TOOL_INPUT` - JSON with tool parameters (for Task: agent type, description, etc.)
- `CLAUDE_TOOL_OUTPUT` - Tool result
- `CLAUDE_TOOL_NAME` - Tool being used
- `PPID` - Parent process ID (useful for temp files)

### Hook Types We'll Use
- `PreToolUse` with matcher `Task` - Agent spawning
- `PostToolUse` with matcher `Task` - Agent completion
- `PostToolUse` with matcher `*` - All tool completions
- `PreToolUse` with matcher `AskUserQuestion` - Input requests

---

## Improvement 1: Simplify Session Discovery

**Problem:** Original plan had hooks emit session_start events, but sessions don't have a dedicated start hook.

**Solution:** Derive session existence from first agent event.

```
First agent event for session X → Create session in state
No events for 30s + all agents done → Mark session ended
```

Benefits:
- No separate session tracking needed
- Session working_dir comes from first agent's context
- Simpler hook configuration

---

## Improvement 2: Graceful Degradation

**Problem:** What happens if dashboard isn't running when hooks fire?

**Solution:** Hooks should fail silently.

```bash
#!/bin/bash
# Hook script with graceful fallback

SOCKET="$HOME/.cache/claude-agent-viz/viz.sock"

# Check if dashboard is running (socket exists and accepting connections)
if [ -S "$SOCKET" ]; then
    echo "$CLAUDE_TOOL_INPUT" | nc -U "$SOCKET" 2>/dev/null || true
fi

# Always exit 0 to not block Claude Code
exit 0
```

Benefits:
- Claude Code never blocked by visualizer
- No error messages when dashboard is off
- Optional monitoring (install hooks, run dashboard when you want to observe)

---

## Improvement 3: Late-Join Support

**Problem:** If user starts dashboard after Claude sessions are running, they miss existing agents.

**Solution:** Hooks write to both socket AND a state file. Dashboard reads state file on startup.

```
Hooks emit to:
  1. Socket (if dashboard running) - for real-time
  2. State file (always) - for late-join recovery

Dashboard on startup:
  1. Read state file to recover existing sessions
  2. Start listening on socket for new events
  3. Clear state file on clean shutdown
```

State file location: `~/.cache/claude-agent-viz/state.json`

Structure:
```json
{
  "sessions": {
    "sess_abc123": {
      "working_dir": "/Users/vijay/project",
      "started_at": "2025-01-15T17:00:00Z",
      "agents": {
        "agent_def456": {
          "type": "Explore",
          "status": "running",
          "parent_id": null
        }
      }
    }
  },
  "last_updated": "2025-01-15T17:15:00Z"
}
```

Benefits:
- Can start dashboard anytime and see current state
- Survives dashboard restart
- Easy to debug (human-readable JSON)

---

## Improvement 4: AskUserQuestion Handling

**Problem:** How do we intercept and respond to input requests?

**Analysis:** `AskUserQuestion` is a tool call. We can:
1. Hook `PreToolUse` to detect when it's called
2. The tool likely presents options and waits for terminal input

**Challenge:** Claude Code expects input from the terminal, not from us.

**Possible Solutions:**

### Option A: Display-Only Mode (MVP)
- Just show that an agent is waiting for input
- User switches to that terminal and responds normally
- Dashboard shows notification, doesn't handle response

### Option B: Terminal Multiplexing (Advanced)
- Like claude-canvas: use tmux to have dashboard in split pane
- Dashboard can potentially inject keystrokes? (complex)

### Option C: Hook the Response (Requires Claude Code changes)
- Would need Claude Code to support external response injection
- Not currently possible with standard hooks

**Recommendation for MVP:** Option A (display-only). Show the notification, let user handle input in the original terminal. Can add Option B later if needed.

---

## Improvement 5: Reduce Dependencies

**Problem:** Original plan had many dependencies (aiosqlite, watchfiles, etc.)

**Revised Dependencies:**
```toml
dependencies = [
    "textual>=0.50.0",    # TUI (required)
    "click>=8.1.0",       # CLI (required)
    "pydantic>=2.0.0",    # Data validation (nice to have)
]
```

Removed:
- `aiosqlite` - No database
- `watchfiles` - Using sockets instead of file watching
- `rich` - Textual includes rich

The emitter (`claude-viz-emit`) should be as lightweight as possible:
- Pure Python, no dependencies beyond stdlib
- Just sends JSON to socket or writes to file
- Fast startup, fast execution

---

## Improvement 6: Simplified Event Schema

**Original:** Complex envelope with many fields.

**Revised:** Minimal events with only essential data.

```python
# Event types
@dataclass
class AgentStartEvent:
    session_id: str
    agent_id: str
    agent_type: str      # Explore, Plan, Bash, etc.
    description: str
    parent_id: str | None
    working_dir: str     # Only on first agent

@dataclass
class AgentEndEvent:
    session_id: str
    agent_id: str
    status: str          # completed, failed

@dataclass
class ToolUseEvent:
    session_id: str
    agent_id: str
    tool_name: str
    status: str          # running, completed, failed

@dataclass
class InputRequestEvent:
    session_id: str
    agent_id: str
    prompt: str
    options: list[str] | None
```

No separate session events - derive from agent events.

---

## Improvement 7: Simpler IPC Protocol

**Original:** Separate sockets for events vs responses.

**Revised:** Single socket, message types distinguish direction.

```json
// Event from hook to dashboard
{"type": "event", "event_type": "agent_start", "data": {...}}

// Query from dashboard (future: for late-join)
{"type": "query", "query_type": "state"}

// Response to query
{"type": "response", "data": {...}}
```

Single socket: `~/.cache/claude-agent-viz/viz.sock`

---

## Improvement 8: Installation UX

**Problem:** User needs to run `claude-viz init` to install hooks.

**Solution:** Auto-detect and prompt.

```
$ claude-viz

⚠ Claude Code hooks not installed.
  Run 'claude-viz init' to enable agent tracking.

  Starting in demo mode with sample data...
```

Or even better:
```
$ claude-viz

⚠ Claude Code hooks not installed.
  Would you like to install them now? [Y/n]
```

Benefits:
- First-run experience is smooth
- User understands what's happening
- Demo mode lets them see the UI before committing

---

## Revised Implementation Order

### Phase 1: Core TUI (No Hooks)
Build the dashboard with mock data first:
- Session tree widget
- Detail panel
- Status indicators
- Demo mode with fake agents

Benefit: Can iterate on UI without hook complexity.

### Phase 2: Event Collection
Add hooks and real data:
- Event emitter (minimal, fast)
- Socket server in dashboard
- State file for late-join
- Hook installer

### Phase 3: Polish
- Input request notifications
- Filtering
- Keyboard shortcuts
- Error handling

---

## Open Questions

1. **Agent ID Source:** Does the Task tool input include an agent ID, or do we generate one?
   - Hypothesis: Generate from hash of session_id + timestamp + description

2. **Parent Agent Detection:** How do we know which agent spawned another?
   - Hypothesis: Track "current agent" per session, new agents are children of current

3. **Token Tracking:** Can we get token usage from hooks?
   - Hypothesis: Probably not directly available in hook environment variables
   - Alternative: Skip token tracking in MVP

4. **Working Directory:** Where do we get the session's working directory?
   - Hypothesis: PWD environment variable in hook script

---

# Plan Improvements - Iteration 2

## Improvement 9: Build TUI First with Demo Mode

**Rationale:** The TUI is the user-facing part. Building it first allows:
- Rapid iteration on the visual design
- Testing without needing hooks
- Showing users what they'll get before installing hooks

**Demo Mode Implementation:**

```python
# src/claude_agent_viz/demo.py
def create_demo_state() -> State:
    """Create realistic demo data for testing the UI."""
    return State(
        sessions={
            "demo-session-1": Session(
                id="demo-session-1",
                working_dir="~/projects/myapp",
                started_at=datetime.now() - timedelta(minutes=5),
                agents=[
                    Agent(
                        id="agent-1",
                        type="Explore",
                        description="Find authentication files",
                        status=AgentStatus.RUNNING,
                        tool_uses=[
                            ToolUse(name="Grep", status="completed"),
                            ToolUse(name="Read", status="running"),
                        ]
                    ),
                    Agent(
                        id="agent-2",
                        parent_id="agent-1",
                        type="Plan",
                        description="Design auth flow",
                        status=AgentStatus.WAITING_INPUT,
                        input_request=InputRequest(
                            prompt="Which auth method?",
                            options=["OAuth", "JWT", "Session"]
                        )
                    ),
                ]
            )
        }
    )
```

CLI flag: `claude-viz --demo`

---

## Improvement 10: Modular Architecture

**Problem:** Tight coupling makes testing hard.

**Solution:** Clear separation of concerns with dependency injection.

```
┌─────────────────────────────────────────────────────────────┐
│                         TUI Layer                           │
│  (app.py, widgets/*)                                        │
│  - Pure rendering, no I/O                                   │
│  - Receives State, renders it                               │
└─────────────────────────┬───────────────────────────────────┘
                          │ observes
┌─────────────────────────▼───────────────────────────────────┐
│                       State Store                           │
│  (store/state.py)                                          │
│  - In-memory state                                          │
│  - Observable (notifies TUI of changes)                     │
│  - No I/O                                                   │
└─────────────────────────┬───────────────────────────────────┘
                          │ updated by
┌─────────────────────────▼───────────────────────────────────┐
│                    Event Collector                          │
│  (collector/server.py)                                      │
│  - Socket server                                            │
│  - Parses events, updates State                             │
│  - Handles state file for persistence                       │
└─────────────────────────────────────────────────────────────┘
```

Benefits:
- TUI can be tested with mock State
- State can be tested without TUI
- Collector can be tested without TUI

---

## Improvement 11: Consider Async vs Threading

**Textual is async-native.** We should use async throughout:

```python
class ClaudeAgentVizApp(App):
    async def on_mount(self):
        # Start socket server as async task
        self.socket_task = asyncio.create_task(self.run_socket_server())

    async def run_socket_server(self):
        server = await asyncio.start_unix_server(
            self.handle_connection,
            path=SOCKET_PATH
        )
        async with server:
            await server.serve_forever()

    async def handle_connection(self, reader, writer):
        data = await reader.read(4096)
        event = json.loads(data.decode())
        self.state.apply_event(event)
        # State change triggers UI refresh via reactive
```

Benefits:
- No threading complexity
- Textual's reactive system handles UI updates
- Single event loop

---

## Improvement 12: Reactive State Updates

**Use Textual's reactive system** for automatic UI updates:

```python
class State(Reactive):
    sessions: dict[str, Session] = reactive({})

    def apply_event(self, event: dict):
        # Update sessions dict
        # Textual automatically re-renders watching widgets

class SessionTree(Tree):
    def watch_sessions(self, sessions: dict):
        """Called automatically when state.sessions changes."""
        self.rebuild_tree(sessions)
```

Benefits:
- No manual refresh calls
- UI always in sync with state
- Clean separation of data and presentation

---

## Improvement 13: Event Emitter as Standalone Script

**Problem:** Installing claude-agent-viz just for the emitter is heavy.

**Solution:** Emitter is a self-contained script that can be copied.

```bash
# During `claude-viz init`:
# 1. Copy emitter script to ~/.claude/hooks/claude-viz-emit.py
# 2. Make it executable
# 3. Configure hooks to call it

# The script has zero dependencies (stdlib only)
```

Emitter script (~50 lines):
```python
#!/usr/bin/env python3
"""Minimal event emitter for Claude Agent Visualizer."""
import json
import os
import socket
import sys

SOCKET_PATH = os.path.expanduser("~/.cache/claude-agent-viz/viz.sock")

def emit(event_type: str, data: dict):
    if not os.path.exists(SOCKET_PATH):
        return  # Dashboard not running, fail silently

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.1)  # 100ms timeout
            sock.connect(SOCKET_PATH)
            message = json.dumps({"type": event_type, **data})
            sock.send(message.encode())
    except:
        pass  # Fail silently

if __name__ == "__main__":
    # Parse args or stdin and call emit()
    pass
```

Benefits:
- No pip install needed for hooks to work
- Fast startup (no imports beyond stdlib)
- Easy to audit/understand

---

## Improvement 14: Testing Strategy

### Unit Tests
```python
# test_state.py
def test_agent_start_creates_session():
    state = State()
    state.apply_event({
        "type": "agent_start",
        "session_id": "s1",
        "agent_id": "a1",
        "agent_type": "Explore",
        "working_dir": "/tmp"
    })
    assert "s1" in state.sessions
    assert state.sessions["s1"].agents[0].id == "a1"

# test_tree.py
async def test_tree_renders_sessions():
    async with App().run_test() as pilot:
        app.state.sessions = {"s1": mock_session()}
        tree = app.query_one(SessionTree)
        assert len(tree.root.children) == 1
```

### Integration Tests
```python
# test_integration.py
async def test_event_flow():
    """Test event from socket to UI."""
    app = ClaudeAgentVizApp()
    async with app.run_test() as pilot:
        # Send event to socket
        await send_test_event({"type": "agent_start", ...})
        await pilot.pause()  # Let event process
        assert "agent-1" in app.state.sessions["s1"].agents
```

### Manual Testing
```bash
# Terminal 1: Start dashboard in demo mode
claude-viz --demo

# Terminal 2: Send test events
echo '{"type":"agent_start",...}' | nc -U ~/.cache/claude-agent-viz/viz.sock
```

---

## Improvement 15: Error Handling & Logging

**Problem:** Silent failures make debugging hard.

**Solution:** Structured logging with configurable verbosity.

```python
# In dashboard
import logging

logger = logging.getLogger("claude-viz")

# On socket error
logger.warning("Failed to parse event: %s", raw_data[:100])

# On state error
logger.error("Invalid agent state transition: %s -> %s", old, new)
```

Log levels:
- `--quiet`: Errors only
- (default): Warnings and errors
- `--verbose`: Info level
- `--debug`: Debug level (includes raw events)

Log file: `~/.cache/claude-agent-viz/viz.log`

---

## Revised File List

Based on all improvements, here's the streamlined file list:

```
src/claude_agent_viz/
├── __init__.py
├── __main__.py
├── cli.py              # Click CLI with --demo flag
├── config.py           # Configuration (optional)
├── state.py            # In-memory state (Observable)
├── demo.py             # Demo data generator
├── collector/
│   ├── __init__.py
│   ├── server.py       # Async socket server
│   └── emitter.py      # Standalone emitter script (copied to hooks)
├── tui/
│   ├── __init__.py
│   ├── app.py          # Main Textual app
│   ├── styles.tcss     # Styling
│   └── widgets/
│       ├── __init__.py
│       ├── session_tree.py
│       ├── detail_panel.py
│       ├── status_bar.py
│       └── input_modal.py
└── hooks/
    ├── __init__.py
    ├── installer.py    # Hook setup
    └── templates/      # Shell script templates
        └── emit.sh
```

Total: ~15 files, focused and minimal.

---

## Final Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  User's Machine                                  │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         Claude Code Sessions                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                       │   │
│  │  │ Session 1   │  │ Session 2   │  │ Session 3   │                       │   │
│  │  │ ~/myapp     │  │ ~/api       │  │ ~/docs      │                       │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                       │   │
│  │         │                │                │                               │   │
│  │         └────────────────┼────────────────┘                               │   │
│  │                          │                                                │   │
│  │                          ▼                                                │   │
│  │              ┌─────────────────────────┐                                  │   │
│  │              │    claude-viz-emit.py   │  (copied to ~/.claude/hooks/)   │   │
│  │              │    - Zero dependencies  │                                  │   │
│  │              │    - Fails silently     │                                  │   │
│  │              └────────────┬────────────┘                                  │   │
│  │                           │                                               │   │
│  └───────────────────────────┼───────────────────────────────────────────────┘   │
│                              │                                                   │
│                              │ JSON events via Unix socket                       │
│                              ▼                                                   │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                    Claude Agent Visualizer (Dashboard)                     │  │
│  │                                                                            │  │
│  │  ┌──────────────────┐    ┌────────────────┐    ┌────────────────────────┐ │  │
│  │  │   Socket Server  │───▶│  State Store   │───▶│   Textual TUI          │ │  │
│  │  │   (async)        │    │  (reactive)    │    │   - Session Tree       │ │  │
│  │  └──────────────────┘    └────────────────┘    │   - Detail Panel       │ │  │
│  │                                                │   - Status Indicators  │ │  │
│  │  ~/.cache/claude-agent-viz/viz.sock           │   - Input Notifications │ │  │
│  │                                                └────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```
