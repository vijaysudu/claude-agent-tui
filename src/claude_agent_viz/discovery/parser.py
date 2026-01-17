"""Parser for Claude Code JSONL session files.

Extracts session information, tool uses, and agent activity from session files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..logging import get_logger
from ..store.models import ToolCategory, ToolStatus

log = get_logger("parser")


@dataclass
class ParsedToolUse:
    """Tool use extracted from session JSONL."""

    tool_id: str
    tool_name: str
    tool_category: ToolCategory
    parameters: dict[str, Any]
    started_at: datetime
    status: ToolStatus = ToolStatus.COMPLETED


@dataclass
class ParsedSession:
    """Full session data from JSONL parsing."""

    session_id: str
    cwd: str
    slug: str  # Human-readable name like "parallel-pondering-bird"
    git_branch: str | None
    summary: str  # From first summary entry
    started_at: datetime
    last_activity: datetime
    tool_uses: list[ParsedToolUse] = field(default_factory=list)
    is_active: bool = False  # Based on modification time + process check
    message_count: int = 0
    file_path: Path | None = None


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO timestamp string to datetime.

    Returns a timezone-naive datetime in local time for consistency
    with datetime.now() used elsewhere in the codebase.
    """
    # Handle ISO format with Z suffix (UTC)
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(ts)
        # Convert to local time and strip timezone info for naive datetime
        if dt.tzinfo is not None:
            # Convert UTC to local time
            local_dt = dt.astimezone()
            return local_dt.replace(tzinfo=None)
        return dt
    except ValueError:
        return datetime.now()


def _determine_tool_category(tool_name: str) -> ToolCategory:
    """Determine the category of a tool from its name."""
    if tool_name.startswith("mcp__"):
        return ToolCategory.MCP
    elif tool_name.startswith("/") or "__" in tool_name:
        return ToolCategory.SKILL
    else:
        return ToolCategory.BUILTIN


def parse_session(file_path: Path) -> ParsedSession | None:
    """Parse a JSONL session file into a ParsedSession object.

    Args:
        file_path: Path to the JSONL session file

    Returns:
        ParsedSession object or None if parsing fails
    """
    if not file_path.exists():
        log.warning(f"Session file not found: {file_path}")
        return None

    session_id = file_path.stem
    summary = ""
    slug = ""
    git_branch = None
    cwd = ""
    started_at = None
    last_activity = None
    tool_uses: list[ParsedToolUse] = []
    message_count = 0

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type", "")
                timestamp_str = entry.get("timestamp")

                if timestamp_str:
                    timestamp = _parse_timestamp(timestamp_str)
                    if started_at is None:
                        started_at = timestamp
                    last_activity = timestamp

                # Extract summary
                if entry_type == "summary" and not summary:
                    summary = entry.get("summary", "")

                # Extract session metadata
                if "sessionId" in entry:
                    session_id = entry["sessionId"]
                if "slug" in entry and not slug:
                    slug = entry["slug"]
                if "gitBranch" in entry and entry["gitBranch"]:
                    git_branch = entry["gitBranch"]
                if "cwd" in entry and not cwd:
                    cwd = entry["cwd"]

                # Count messages
                if entry_type in ("user", "assistant"):
                    message_count += 1

                # Extract tool uses from assistant messages
                if entry_type == "assistant":
                    message = entry.get("message", {})
                    content = message.get("content", [])

                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "tool_use":
                                tool_id = item.get("id", "")
                                tool_name = item.get("name", "Unknown")
                                tool_input = item.get("input", {})

                                tool_timestamp = (
                                    _parse_timestamp(timestamp_str)
                                    if timestamp_str
                                    else datetime.now()
                                )
                                tool_uses.append(
                                    ParsedToolUse(
                                        tool_id=tool_id,
                                        tool_name=tool_name,
                                        tool_category=_determine_tool_category(tool_name),
                                        parameters=tool_input if isinstance(tool_input, dict) else {},
                                        started_at=tool_timestamp,
                                    )
                                )

    except OSError as e:
        log.error(f"Failed to read session file {file_path}: {e}")
        return None

    # Fallback for missing timestamps
    if started_at is None:
        started_at = datetime.fromtimestamp(file_path.stat().st_mtime)
    if last_activity is None:
        last_activity = started_at

    return ParsedSession(
        session_id=session_id,
        cwd=cwd,
        slug=slug or session_id[:8],
        git_branch=git_branch,
        summary=summary or "No summary available",
        started_at=started_at,
        last_activity=last_activity,
        tool_uses=tool_uses,
        message_count=message_count,
        file_path=file_path,
    )


def parse_incremental(
    file_path: Path,
    last_offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Parse only new lines since last read.

    For efficient real-time updates, this reads from a specific byte offset
    and returns only new entries.

    Args:
        file_path: Path to the JSONL session file
        last_offset: Byte offset to start reading from

    Returns:
        Tuple of (list of new entries as dicts, new offset)
    """
    if not file_path.exists():
        return [], 0

    new_entries: list[dict[str, Any]] = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            f.seek(last_offset)
            content = f.read()
            new_offset = f.tell()

            for line in content.split("\n"):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    new_entries.append(entry)
                except json.JSONDecodeError:
                    continue

    except OSError as e:
        log.error(f"Failed to read session file {file_path}: {e}")
        return [], last_offset

    return new_entries, new_offset


def get_session_summary(file_path: Path) -> str | None:
    """Quick extraction of just the session summary.

    More efficient than full parsing when only summary is needed.
    """
    if not file_path.exists():
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    if entry.get("type") == "summary":
                        return entry.get("summary")
                except json.JSONDecodeError:
                    continue

    except OSError:
        pass

    return None
