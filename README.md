# Claude Agent Visualizer

A real-time terminal dashboard for visualizing Claude Code agent activity across multiple sessions.

```
┌─ Claude Agent Visualizer ─────────────────────────────────────────────────────┐
│ Sessions: 3 active │ Agents: 12 total │ 2 awaiting input │ ↻ Live           │
├───────────────────────────────────────────────────────────────────────────────┤
│ ▼ ~/projects/myapp (session: abc123)                          [5m 32s]       │
│   ├─● Root Agent                                    ██████░░ 15.2k tokens    │
│   │  ├─● Explore: "Find authentication files"                   running      │
│   │  │  └─○ Grep: pattern="auth" → 12 files                    completed     │
│   │  └─◐ Plan: "Design login flow"                          awaiting input   │
│   │        └─ ? "Which auth method: OAuth or JWT?"                           │
│   └─○ Bash: "npm test" → exit 0                                completed     │
│                                                                               │
│ ▶ ~/projects/api (session: def456)                            [2m 15s]       │
│ ▶ ~/projects/docs (session: ghi789)                           [0m 45s]       │
├───────────────────────────────────────────────────────────────────────────────┤
│ [q] Quit │ [r] Refresh │ [n] New │ [Space] Expand │ [Tab] Next │ [?] Help    │
└───────────────────────────────────────────────────────────────────────────────┘
```

## Features

- **Hierarchical Agent View**: See main orchestration agent and all spawned subagents in a tree
- **Real-time Updates**: Watch agents spawn, work, and complete via file-watching
- **No Setup Required**: Reads directly from Claude Code's session files - no hooks needed
- **Tool Tracking**: See commands, skills, and MCP tools being used
- **Status Colors**: Visual distinction between running, completed, failed, and waiting states
- **Multi-Session Support**: Monitor multiple Claude Code sessions simultaneously
- **Session Spawning**: Launch new Claude sessions from the dashboard (press `n`)
- **Session History**: View recent sessions from the last 24 hours

## Installation

```bash
# Clone and install
git clone <your-repo-url>
cd claude-agent-viz
pip install -e .
```

## Quick Start

### Start the Dashboard

```bash
claude-viz
```

The dashboard automatically discovers and displays Claude Code sessions by reading from `~/.claude/projects/`.

### Demo Mode

To see the visualizer with sample data (no Claude Code needed):

```bash
claude-viz --demo
```

### List Sessions

```bash
# Show recent sessions
claude-viz scan

# Show more sessions
claude-viz scan --max-sessions=100 --max-age=48
```

### Spawn New Session

```bash
# Spawn in current directory
claude-viz spawn

# Spawn in specific directory
claude-viz spawn /path/to/project
```

## Requirements

- Python 3.11+
- Claude Code (any recent version)
- Terminal with 256-color support (most modern terminals)
- macOS with Terminal.app, iTerm2, or tmux (for session spawning)

## How It Works

The visualizer reads Claude Code's session JSONL files directly - no hooks or extra setup required.

```
~/.claude/projects/
├── -Users-name-project-a/
│   ├── abc123.jsonl          # Session file
│   └── def456.jsonl
└── -Users-name-project-b/
    └── ghi789.jsonl
```

**Session Detection**:
1. **File Scanning**: Scans `~/.claude/projects/` for session files
2. **File Watching**: Uses `watchfiles` to detect changes in real-time
3. **Activity Detection**: Sessions are "active" if modified in last 60 seconds or a Claude process is running

**Session File Format**:
Each line in a `.jsonl` file contains an event with:
- `type`: "summary", "user", "assistant", "system"
- `sessionId`: UUID of the session
- `cwd`: Working directory
- `timestamp`: ISO format timestamp
- `slug`: Human-readable name like "parallel-pondering-bird"
- `message.content`: Tool uses, text responses

## CLI Commands

```bash
# Start the dashboard
claude-viz

# Start with demo data
claude-viz --demo

# Enable verbose logging
claude-viz -v

# List recent sessions
claude-viz scan
claude-viz scan --max-sessions=50 --max-age=24

# Spawn new session
claude-viz spawn              # In current directory
claude-viz spawn /path/to/dir # In specific directory
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh session list |
| `n` | Spawn new session in current directory |
| `Space` | Expand/collapse selected node |
| `Tab` | Jump to next session |
| `Shift+Tab` | Jump to previous session |
| `?` | Show help |

## Status Icons

| Icon | Meaning |
|------|---------|
| `●` | Running / Active |
| `○` | Completed |
| `✗` | Failed |
| `◐` | Waiting for input |

## File Locations

- **Session Files**: `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`
- **Logs**: `~/.cache/claude-agent-viz/viz.log`

## Development

```bash
# Clone the repository
git clone <your-repo-url>
cd claude-agent-viz

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .

# Run tests
pytest

# Run with demo data
claude-viz --demo

# Run with verbose logging
claude-viz -v
```

## Architecture

```
src/claude_agent_viz/
├── cli.py              # CLI entry point
├── state.py            # Application state management
├── demo.py             # Demo data generator
├── discovery/          # Session discovery
│   ├── scanner.py      # Scan ~/.claude/projects/
│   ├── parser.py       # Parse JSONL session files
│   └── watcher.py      # Watch for file changes
├── spawner/            # Session spawning
│   └── terminal.py     # Terminal detection & launching
├── store/
│   └── models.py       # Data models
└── tui/
    ├── app.py          # Textual application
    └── widgets/        # UI components
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and component overview
- [Data Model](docs/DATA_MODEL.md) - Event schema and data structures
- [UI Design](docs/UI_DESIGN.md) - TUI layout and component details

## License

MIT
