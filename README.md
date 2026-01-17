# Claude Agent Visualizer

A terminal UI for visualizing and interacting with Claude agent sessions.

## Features

- View Claude session transcripts with tool uses
- See full content of file reads, edits, and command outputs
- Spawn new Claude sessions (embedded or external terminal)
- Kill running Claude sessions

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Run with real sessions from ~/.claude/projects
claude-viz

# Run with demo data
claude-viz --demo

# Specify a custom sessions directory
claude-viz -d /path/to/sessions
```

## Keybindings

| Key | Action |
|-----|--------|
| `n` | New session (uses current mode) |
| `k` | Kill selected session |
| `t` | Toggle spawn mode (embedded/external) |
| `r` | Refresh sessions |
| `q` | Quit |
| `?` | Show help |

## Requirements

- Python 3.10+
- Textual
- Rich
