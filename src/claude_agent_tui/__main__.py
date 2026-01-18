"""CLI entry point for Claude Agent Visualizer."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def get_default_sessions_dir() -> Path:
    """Get the default Claude sessions directory."""
    home = Path.home()
    claude_dir = home / ".claude" / "projects"
    return claude_dir


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="claude-tui",
        description="Visualize Claude agent sessions in a TUI",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with demo data",
    )
    parser.add_argument(
        "--sessions-dir",
        "-d",
        type=Path,
        default=None,
        help="Directory containing session JSONL files",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    args = parser.parse_args()

    # Determine sessions directory
    sessions_dir = args.sessions_dir
    if sessions_dir is None and not args.demo:
        sessions_dir = get_default_sessions_dir()

    # Import app here to avoid import errors if dependencies aren't installed
    try:
        from .tui.app import ClaudeAgentVizApp
    except ImportError as e:
        print(f"Error: Missing dependencies. Install with: pip install claude-agent-tui[tui]")
        print(f"Details: {e}")
        return 1

    # Create and run app
    app = ClaudeAgentVizApp(
        sessions_dir=sessions_dir,
        demo_mode=args.demo,
    )

    try:
        app.run()
    except Exception as e:
        print(f"Error running application: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
