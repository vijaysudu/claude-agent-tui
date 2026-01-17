# Implementation Plan

## Overview

This document outlines the phased implementation approach for Claude Agent Visualizer, from MVP to full feature set.

---

## Phase 1: Project Foundation

**Goal:** Set up project structure, dependencies, and basic infrastructure.

### 1.1 Project Setup

```
claude-agent-viz/
├── src/
│   └── claude_agent_viz/
│       ├── __init__.py
│       ├── __main__.py          # Entry point
│       ├── cli.py               # CLI commands
│       ├── config.py            # Configuration management
│       ├── collector/
│       │   ├── __init__.py
│       │   ├── emitter.py       # Hook event emitter
│       │   └── watcher.py       # Database watcher
│       ├── store/
│       │   ├── __init__.py
│       │   ├── database.py      # SQLite operations
│       │   └── models.py        # Pydantic/dataclass models
│       ├── tui/
│       │   ├── __init__.py
│       │   ├── app.py           # Main Textual app
│       │   ├── styles.tcss      # Textual CSS
│       │   └── widgets/
│       │       ├── __init__.py
│       │       ├── session_tree.py
│       │       ├── detail_panel.py
│       │       ├── status_bar.py
│       │       └── input_modal.py
│       └── hooks/
│           ├── __init__.py
│           ├── installer.py     # Hook installation
│           └── templates/       # Hook script templates
├── tests/
│   ├── __init__.py
│   ├── test_emitter.py
│   ├── test_database.py
│   └── test_tui.py
├── pyproject.toml
├── README.md
└── docs/
```

### 1.2 Dependencies

```toml
# pyproject.toml
[project]
name = "claude-agent-viz"
version = "0.1.0"
description = "Real-time terminal visualizer for Claude Code agents"
requires-python = ">=3.11"
dependencies = [
    "textual>=0.50.0",           # TUI framework
    "click>=8.1.0",              # CLI framework
    "pydantic>=2.0.0",           # Data validation
    "watchfiles>=0.21.0",        # Efficient file watching
    "aiosqlite>=0.19.0",         # Async SQLite
    "rich>=13.0.0",              # Terminal formatting
    "tomli>=2.0.0",              # TOML parsing (config)
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-textual-snapshot>=0.4.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
]

[project.scripts]
claude-viz = "claude_agent_viz.cli:main"
claude-viz-emit = "claude_agent_viz.collector.emitter:main"
```

### 1.3 Configuration System

```python
# src/claude_agent_viz/config.py
from pathlib import Path
from pydantic import BaseModel

class DisplayConfig(BaseModel):
    refresh_rate_ms: int = 100
    max_sessions: int = 10
    tree_indent: int = 2

class ColorsConfig(BaseModel):
    running: str = "yellow"
    completed: str = "green"
    failed: str = "red"
    waiting_input: str = "blue"

class StorageConfig(BaseModel):
    db_path: Path = Path("~/.local/share/claude-agent-viz/events.db")
    retention_hours: int = 24

class Config(BaseModel):
    display: DisplayConfig = DisplayConfig()
    colors: ColorsConfig = ColorsConfig()
    storage: StorageConfig = StorageConfig()

def load_config() -> Config:
    """Load config from file or return defaults."""
    config_path = Path("~/.config/claude-agent-viz/config.toml").expanduser()
    if config_path.exists():
        import tomli
        with open(config_path, "rb") as f:
            data = tomli.load(f)
        return Config(**data)
    return Config()
```

### 1.4 Deliverables

- [ ] Project structure created
- [ ] pyproject.toml with all dependencies
- [ ] Configuration system working
- [ ] Basic CLI skeleton (`claude-viz --help`)

---

## Phase 2: Event Collection

**Goal:** Implement the hook system and event emitter.

### 2.1 Event Emitter CLI

```python
# src/claude_agent_viz/collector/emitter.py
#!/usr/bin/env python3
"""
Lightweight event emitter called by Claude Code hooks.
Designed for minimal latency (<50ms).
"""
import sys
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("~/.local/share/claude-agent-viz/events.db").expanduser()

def emit_event(event_type: str, payload: dict):
    """Write event to SQLite database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO events (event_type, timestamp, payload)
            VALUES (?, ?, ?)
        """, (event_type, datetime.now().isoformat(), json.dumps(payload)))

def main():
    """CLI entry point."""
    import click

    @click.group()
    def cli():
        pass

    @cli.command()
    @click.argument('session_id')
    @click.argument('working_dir')
    def session_start(session_id: str, working_dir: str):
        emit_event('session_start', {
            'session_id': session_id,
            'working_dir': working_dir,
            'pid': os.getpid(),
        })

    @cli.command()
    @click.option('--stdin', is_flag=True, help='Read event from stdin')
    def agent_start(stdin: bool):
        if stdin:
            payload = json.load(sys.stdin)
        else:
            # Parse from environment variables set by hooks
            payload = parse_hook_env()
        emit_event('agent_start', payload)

    # ... more commands

    cli()
```

### 2.2 Claude Code Hook Templates

```bash
# hooks/templates/pre_tool_use.sh
#!/bin/bash
# Pre-tool-use hook for Claude Agent Visualizer

TOOL_NAME="$CLAUDE_TOOL_NAME"
TOOL_INPUT="$CLAUDE_TOOL_INPUT"
SESSION_ID="$CLAUDE_SESSION_ID"

# Only emit for Task tool (agent spawning)
if [ "$TOOL_NAME" = "Task" ]; then
    echo "$TOOL_INPUT" | claude-viz-emit agent-start --stdin
fi
```

```bash
# hooks/templates/post_tool_use.sh
#!/bin/bash
# Post-tool-use hook for Claude Agent Visualizer

TOOL_NAME="$CLAUDE_TOOL_NAME"
TOOL_OUTPUT="$CLAUDE_TOOL_OUTPUT"
SESSION_ID="$CLAUDE_SESSION_ID"

# Emit tool completion
claude-viz-emit tool-complete \
    --tool "$TOOL_NAME" \
    --session "$SESSION_ID" \
    --output-preview "${TOOL_OUTPUT:0:200}"
```

### 2.3 Hook Installer

```python
# src/claude_agent_viz/hooks/installer.py
import json
from pathlib import Path

CLAUDE_SETTINGS = Path("~/.claude/settings.json").expanduser()

def install_hooks():
    """Add visualizer hooks to Claude Code settings."""
    # Load existing settings
    if CLAUDE_SETTINGS.exists():
        with open(CLAUDE_SETTINGS) as f:
            settings = json.load(f)
    else:
        settings = {}

    # Add our hooks
    hooks = settings.setdefault("hooks", {})

    hooks["PreToolUse"] = hooks.get("PreToolUse", []) + [{
        "matcher": "Task",
        "commands": ["claude-viz-emit agent-start --from-env"]
    }]

    hooks["PostToolUse"] = hooks.get("PostToolUse", []) + [{
        "matcher": "*",
        "commands": ["claude-viz-emit tool-complete --from-env"]
    }]

    # Save settings
    with open(CLAUDE_SETTINGS, "w") as f:
        json.dump(settings, f, indent=2)

    print(f"✓ Hooks installed in {CLAUDE_SETTINGS}")
```

### 2.4 Deliverables

- [ ] Event emitter CLI (`claude-viz-emit`)
- [ ] Hook templates for all event types
- [ ] Hook installer (`claude-viz init`)
- [ ] SQLite database schema created on first run
- [ ] Unit tests for emitter

---

## Phase 3: TUI Foundation

**Goal:** Build the core Textual application with basic visualization.

### 3.1 Main Application

```python
# src/claude_agent_viz/tui/app.py
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static

from .widgets.session_tree import SessionTree
from .widgets.detail_panel import DetailPanel
from .widgets.status_bar import StatusBar

class ClaudeAgentVizApp(App):
    """Main TUI application."""

    CSS_PATH = "styles.tcss"
    TITLE = "Claude Agent Visualizer"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("space", "toggle_expand", "Expand/Collapse"),
        ("tab", "next_session", "Next Session"),
        ("enter", "select_or_respond", "Select/Respond"),
        ("?", "show_help", "Help"),
    ]

    def __init__(self):
        super().__init__()
        self.sessions: list[Session] = []

    def compose(self) -> ComposeResult:
        yield StatusBar()
        yield Horizontal(
            SessionTree(id="session-tree"),
            DetailPanel(id="detail-panel"),
        )
        yield Footer()

    async def on_mount(self):
        """Start background workers when app mounts."""
        self.run_worker(self.watch_database())

    async def watch_database(self):
        """Background worker to poll database for changes."""
        from ..store.database import get_sessions

        while True:
            sessions = await get_sessions()
            if sessions != self.sessions:
                self.sessions = sessions
                self.query_one("#session-tree", SessionTree).update_sessions(sessions)
                self.query_one(StatusBar).update_stats(sessions)
            await asyncio.sleep(0.1)

    def on_session_tree_node_selected(self, event: SessionTree.NodeSelected):
        """Handle tree node selection."""
        self.query_one("#detail-panel", DetailPanel).show(event.node.data)
```

### 3.2 Session Tree Widget

```python
# src/claude_agent_viz/tui/widgets/session_tree.py
from textual.widgets import Tree
from textual.widgets.tree import TreeNode
from rich.text import Text

from ...store.models import Session, Agent, AgentStatus

class SessionTree(Tree):
    """Hierarchical tree of sessions and agents."""

    class NodeSelected(Message):
        """Message sent when a node is selected."""
        def __init__(self, node: TreeNode):
            self.node = node
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__("Sessions", **kwargs)
        self.guide_depth = 3

    def update_sessions(self, sessions: list[Session]):
        """Rebuild tree with new session data."""
        # Remember expanded state
        expanded = {node.data.id for node in self._get_all_nodes() if node.is_expanded}

        self.clear()
        for session in sessions:
            self._add_session(session, expanded)

    def _add_session(self, session: Session, expanded: set[str]):
        """Add a session node to the tree."""
        label = self._format_session_label(session)
        node = self.root.add(label, data=session)
        node.expand() if session.id in expanded or session.status == "active" else None

        if session.root_agent:
            self._add_agent(node, session.root_agent, expanded)

    def _add_agent(self, parent: TreeNode, agent: Agent, expanded: set[str]):
        """Recursively add agent nodes."""
        label = self._format_agent_label(agent)
        node = parent.add(label, data=agent)

        should_expand = (
            agent.id in expanded or
            agent.status in (AgentStatus.RUNNING, AgentStatus.WAITING_INPUT)
        )
        if should_expand:
            node.expand()

        # Add tool uses (last 5)
        for tool in agent.tool_uses[-5:]:
            tool_label = self._format_tool_label(tool)
            node.add_leaf(tool_label, data=tool)

        # Add pending input requests
        for req in agent.input_requests:
            if req.status == "pending":
                req_label = Text.assemble(
                    ("? ", "blue bold"),
                    (f'"{req.prompt[:40]}..."', "italic"),
                )
                node.add_leaf(req_label, data=req)

        # Recurse for children
        for child in agent.children:
            self._add_agent(node, child, expanded)

    def _format_session_label(self, session: Session) -> Text:
        dir_name = Path(session.working_dir).name
        duration = self._format_duration(session.duration)
        return Text.assemble(
            (dir_name, "bold"),
            " ",
            (duration, "dim"),
        )

    def _format_agent_label(self, agent: Agent) -> Text:
        icon = {
            AgentStatus.RUNNING: ("●", "yellow"),
            AgentStatus.COMPLETED: ("○", "green"),
            AgentStatus.FAILED: ("✗", "red"),
            AgentStatus.WAITING_INPUT: ("◐", "blue bold"),
        }[agent.status]

        return Text.assemble(
            icon,
            " ",
            (agent.agent_type, "bold"),
            ": ",
            (agent.description[:25], ""),
        )
```

### 3.3 Styles

```tcss
/* src/claude_agent_viz/tui/styles.tcss */

Screen {
    background: #1a1b26;
}

StatusBar {
    dock: top;
    height: 1;
    background: #24283b;
    color: #c0caf5;
    padding: 0 1;
}

StatusBar .alert {
    color: #e0af68;
    text-style: bold;
}

#session-tree {
    width: 40%;
    height: 100%;
    border: solid #414868;
    background: #1a1b26;
}

#detail-panel {
    width: 60%;
    height: 100%;
    border: solid #414868;
    background: #1a1b26;
    padding: 1;
}

Tree {
    padding: 1;
}

Tree > .tree--cursor {
    background: #414868;
}

.status-running {
    color: #e0af68;
}

.status-completed {
    color: #9ece6a;
}

.status-failed {
    color: #f7768e;
}

.status-waiting {
    color: #7aa2f7;
    text-style: bold;
}
```

### 3.4 Deliverables

- [ ] Main Textual app running
- [ ] Session tree with expand/collapse
- [ ] Detail panel showing selected item
- [ ] Status bar with counts
- [ ] Color-coded status indicators
- [ ] Real-time database polling
- [ ] Keyboard navigation working

---

## Phase 4: Input System

**Goal:** Implement input request notifications and response mechanism.

### 4.1 Input Detection

```python
# In database watcher, detect pending inputs
async def check_pending_inputs(self) -> list[InputRequest]:
    """Check for any pending input requests."""
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute("""
            SELECT * FROM input_requests
            WHERE status = 'pending'
            ORDER BY created_at ASC
        """)
        rows = await cursor.fetchall()
        return [InputRequest.from_row(row) for row in rows]
```

### 4.2 Input Modal

```python
# src/claude_agent_viz/tui/widgets/input_modal.py
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Input, OptionList
from textual.containers import Vertical, Horizontal

class InputModal(ModalScreen):
    """Modal for responding to input requests."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "submit", "Submit"),
    ]

    def __init__(self, request: InputRequest):
        self.request = request
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Static(f"Agent: {self.request.agent_description}", classes="header")
            yield Static(self.request.prompt, classes="question")

            if self.request.options:
                yield OptionList(*[
                    (opt.label, opt.value)
                    for opt in self.request.options
                ])
            else:
                yield Input(placeholder="Enter your response...")

            with Horizontal(classes="buttons"):
                yield Button("Submit", variant="primary", id="submit")
                yield Button("Cancel", variant="default", id="cancel")

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "submit":
            await self.submit_response()
        else:
            self.dismiss()

    async def submit_response(self):
        """Submit the response and close modal."""
        if self.request.options:
            option_list = self.query_one(OptionList)
            response = option_list.highlighted_option.value
        else:
            response = self.query_one(Input).value

        # Write response to bridge
        await write_response(self.request.id, response)

        self.dismiss(response)
```

### 4.3 Response Bridge

```python
# src/claude_agent_viz/collector/bridge.py
from pathlib import Path
import aiofiles

RESPONSES_DIR = Path("~/.local/share/claude-agent-viz/responses").expanduser()

async def write_response(request_id: str, response: str):
    """Write response for Claude Code to read."""
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)

    response_file = RESPONSES_DIR / f"{request_id}.response"
    ready_file = RESPONSES_DIR / f"{request_id}.ready"

    # Write response content
    async with aiofiles.open(response_file, "w") as f:
        await f.write(response)

    # Write ready signal (empty file)
    async with aiofiles.open(ready_file, "w") as f:
        pass

async def poll_for_response(request_id: str, timeout: float = 300) -> str | None:
    """Poll for response (called by Claude Code hook)."""
    ready_file = RESPONSES_DIR / f"{request_id}.ready"
    response_file = RESPONSES_DIR / f"{request_id}.response"

    start = time.time()
    while time.time() - start < timeout:
        if ready_file.exists():
            async with aiofiles.open(response_file) as f:
                response = await f.read()

            # Cleanup
            ready_file.unlink(missing_ok=True)
            response_file.unlink(missing_ok=True)

            return response

        await asyncio.sleep(0.1)

    return None
```

### 4.4 Hook Integration for Input

```python
# Claude Code hook that waits for dashboard response
# This would be triggered when AskUserQuestion is called

async def wait_for_dashboard_response(request_id: str) -> str | None:
    """Called by Claude Code to wait for dashboard response."""
    from claude_agent_viz.collector.bridge import poll_for_response
    return await poll_for_response(request_id)
```

### 4.5 Deliverables

- [ ] Input request detection in database watcher
- [ ] Pulsing indicator in tree for waiting agents
- [ ] Input modal with option selection
- [ ] Input modal with free-text input
- [ ] Response bridge (file-based)
- [ ] Status update after response sent
- [ ] Timeout handling for input requests

---

## Phase 5: Polish & Distribution

**Goal:** Refine UX, add advanced features, and prepare for distribution.

### 5.1 Advanced Features

- **Filtering**: Filter sessions by status, age, or search term
- **History view**: Browse completed sessions
- **Export**: Export session to JSON for debugging
- **Notifications**: Desktop notifications for input requests (optional)

### 5.2 Performance Optimization

- **Incremental updates**: Only refresh changed parts of tree
- **Virtual scrolling**: Handle 100+ agents without lag
- **Connection pooling**: Reuse SQLite connections
- **Lazy loading**: Load tool details on demand

### 5.3 Testing

```python
# tests/test_tui.py
import pytest
from textual.testing import AppTest

from claude_agent_viz.tui.app import ClaudeAgentVizApp

@pytest.fixture
def app():
    return ClaudeAgentVizApp()

async def test_app_starts(app):
    async with app.run_test() as pilot:
        assert app.query_one("#session-tree") is not None
        assert app.query_one("#detail-panel") is not None

async def test_session_tree_updates(app):
    async with app.run_test() as pilot:
        tree = app.query_one("#session-tree")
        # Simulate database update
        app.sessions = [create_mock_session()]
        tree.update_sessions(app.sessions)
        assert len(tree.root.children) == 1

async def test_input_modal_opens(app):
    async with app.run_test() as pilot:
        # Select a node with pending input
        # Press enter
        # Verify modal appears
        pass
```

### 5.4 Distribution

```toml
# pyproject.toml additions for PyPI
[project.urls]
Homepage = "https://github.com/yourusername/claude-agent-viz"
Documentation = "https://github.com/yourusername/claude-agent-viz#readme"
Repository = "https://github.com/yourusername/claude-agent-viz"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

```bash
# Build and publish
python -m build
twine upload dist/*
```

### 5.5 Deliverables

- [ ] Filter/search functionality
- [ ] Session history view
- [ ] Export to JSON
- [ ] Full test coverage
- [ ] Published to PyPI
- [ ] GitHub Actions CI/CD
- [ ] Documentation site

---

## Implementation Timeline

| Phase | Focus | Key Deliverables |
|-------|-------|------------------|
| **Phase 1** | Foundation | Project setup, config, CLI skeleton |
| **Phase 2** | Collection | Event emitter, hooks, database |
| **Phase 3** | Visualization | TUI app, tree, detail panel |
| **Phase 4** | Interaction | Input modal, response bridge |
| **Phase 5** | Polish | Testing, optimization, distribution |

---

## Risk Mitigation

### Risk: Hook Performance

**Concern:** Hooks slow down Claude Code
**Mitigation:** Async emitter, minimal processing, <50ms target

### Risk: Input Bridge Reliability

**Concern:** File-based IPC may have race conditions
**Mitigation:** Two-file protocol (response + ready signal), atomic writes

### Risk: Database Locking

**Concern:** SQLite write conflicts between emitter and reader
**Mitigation:** WAL mode, short transactions, connection timeouts

### Risk: Terminal Compatibility

**Concern:** TUI may not work in all terminals
**Mitigation:** Test on iTerm2, Terminal.app, VS Code terminal, tmux

---

## Success Criteria

1. **MVP**: Can see agent tree and status updates in real-time
2. **v0.1**: Can respond to input requests from dashboard
3. **v0.2**: Full tool tracking and context metrics
4. **v1.0**: Stable, documented, published to PyPI
