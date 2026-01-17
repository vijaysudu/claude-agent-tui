"""Discovery module for finding and parsing Claude Code sessions.

This module provides functionality to:
- Scan ~/.claude/projects/ for session files
- Parse JSONL session files into structured data
- Watch for changes to session files
"""

from .parser import ParsedSession, parse_session, parse_incremental
from .scanner import SessionInfo, scan_sessions, get_active_processes, get_claude_projects_dir
from .watcher import SessionWatcher

__all__ = [
    "ParsedSession",
    "SessionInfo",
    "SessionWatcher",
    "get_active_processes",
    "get_claude_projects_dir",
    "parse_incremental",
    "parse_session",
    "scan_sessions",
]
