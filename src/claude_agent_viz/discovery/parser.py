"""Parser for Claude session JSONL files.

Extracts tool uses and their results from session transcripts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedToolUse:
    """Represents a parsed tool use from a Claude session."""

    tool_use_id: str
    tool_name: str
    input_params: dict[str, Any]
    timestamp: str | None = None

    # Result fields - populated from matching tool_result entry
    result_content: str | None = None
    error_message: str | None = None
    is_error: bool = False

    # Computed preview for display
    preview: str = ""

    def __post_init__(self):
        """Generate preview from input params."""
        if not self.preview:
            self.preview = self._generate_preview()

    def _generate_preview(self) -> str:
        """Generate a short preview based on tool type."""
        params = self.input_params

        if self.tool_name == "Read":
            return params.get("file_path", "")[:80]
        elif self.tool_name == "Edit":
            path = params.get("file_path", "")
            return f"{path} (edit)"[:80]
        elif self.tool_name == "Write":
            path = params.get("file_path", "")
            return f"{path} (write)"[:80]
        elif self.tool_name == "Bash":
            cmd = params.get("command", "")
            return cmd[:80] if len(cmd) <= 80 else cmd[:77] + "..."
        elif self.tool_name == "Grep":
            pattern = params.get("pattern", "")
            path = params.get("path", ".")
            return f"{pattern} in {path}"[:80]
        elif self.tool_name == "Glob":
            pattern = params.get("pattern", "")
            return pattern[:80]
        elif self.tool_name == "Task":
            desc = params.get("description", "")
            return desc[:80]
        else:
            # Generic preview
            if params:
                first_val = str(list(params.values())[0])
                return first_val[:80] if len(first_val) <= 80 else first_val[:77] + "..."
            return ""


@dataclass
class ParsedSession:
    """Represents a parsed Claude session."""

    session_id: str
    session_path: Path
    tool_uses: list[ParsedToolUse] = field(default_factory=list)
    message_count: int = 0
    start_time: str | None = None
    summary: str | None = None  # First user message or task description
    project_path: str | None = None  # Working directory / project path

    @property
    def tool_count(self) -> int:
        """Return the number of tool uses."""
        return len(self.tool_uses)

    @property
    def display_summary(self) -> str:
        """Get a display-friendly summary."""
        if self.summary:
            # Truncate and clean up
            summary = self.summary.strip()
            # Remove newlines
            summary = summary.replace("\n", " ").replace("\r", "")
            # Truncate
            if len(summary) > 60:
                return summary[:57] + "..."
            return summary
        return "No summary available"


def parse_session(jsonl_path: Path) -> ParsedSession:
    """Parse a Claude session JSONL file.

    Args:
        jsonl_path: Path to the JSONL session file.

    Returns:
        ParsedSession containing all tool uses with their results.
    """
    session_id = jsonl_path.stem
    tool_uses: list[ParsedToolUse] = []
    tool_use_map: dict[str, ParsedToolUse] = {}  # Map tool_use_id to ParsedToolUse
    message_count = 0
    start_time: str | None = None
    summary: str | None = None
    project_path: str | None = None
    first_user_message_found = False

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type")
            timestamp = entry.get("timestamp")

            if start_time is None and timestamp:
                start_time = timestamp

            # Extract project path from cwd field (present in user/assistant messages)
            if not project_path and "cwd" in entry:
                project_path = entry["cwd"]

            # Extract project path from system message or init (fallback)
            if entry_type == "system" and not project_path:
                # Look for cwd or working directory in system context
                system_content = entry.get("message", "")
                if isinstance(system_content, str):
                    # Try to find "Working directory:" pattern
                    if "Working directory:" in system_content:
                        idx = system_content.find("Working directory:")
                        end_idx = system_content.find("\n", idx)
                        if end_idx == -1:
                            end_idx = len(system_content)
                        project_path = system_content[idx + 18:end_idx].strip()

            # Count messages
            if entry_type in ("user", "assistant"):
                message_count += 1

            # Extract summary from first real user message
            if entry_type == "user" and not first_user_message_found:
                message = entry.get("message", {})
                content_blocks = message.get("content", [])

                for block in content_blocks:
                    # Skip tool_result blocks - they're not user messages
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        continue

                    # Extract text from user message
                    text = ""
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                    elif isinstance(block, str):
                        text = block.strip()

                    if text:
                        # Skip system tags
                        if text.startswith("<"):
                            continue
                        # Skip continuation summaries
                        if text.startswith("This session is being continued"):
                            continue
                        # Skip context window messages
                        if "context window" in text.lower():
                            continue
                        # Skip very short messages (likely single chars or artifacts)
                        if len(text) < 5:
                            continue

                        summary = text
                        first_user_message_found = True
                        break

            # Extract tool_use from assistant messages
            if entry_type == "assistant":
                message = entry.get("message", {})
                content_blocks = message.get("content", [])

                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_use_id = block.get("id", "")
                        tool_name = block.get("name", "")
                        input_params = block.get("input", {})

                        parsed = ParsedToolUse(
                            tool_use_id=tool_use_id,
                            tool_name=tool_name,
                            input_params=input_params,
                            timestamp=timestamp,
                        )
                        tool_uses.append(parsed)
                        tool_use_map[tool_use_id] = parsed

            # Extract tool_result and match to tool_use
            if entry_type == "user":
                message = entry.get("message", {})
                content_blocks = message.get("content", [])

                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_use_id = block.get("tool_use_id", "")
                        is_error = block.get("is_error", False)
                        content = block.get("content", [])

                        # Extract text content
                        result_text = ""
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                result_text += item.get("text", "")
                            elif isinstance(item, str):
                                result_text += item

                        # Match to tool_use
                        if tool_use_id in tool_use_map:
                            tool_use = tool_use_map[tool_use_id]
                            if is_error:
                                tool_use.is_error = True
                                tool_use.error_message = result_text
                            else:
                                tool_use.result_content = result_text

    # Try to get project path from jsonl path if not found in content
    # ~/.claude/projects/-Users-name-project/session.jsonl
    if not project_path:
        parent_name = jsonl_path.parent.name
        if parent_name.startswith("-"):
            # Convert -Users-name-project to /Users/name/project
            project_path = parent_name.replace("-", "/")

    return ParsedSession(
        session_id=session_id,
        session_path=jsonl_path,
        tool_uses=tool_uses,
        message_count=message_count,
        start_time=start_time,
        summary=summary,
        project_path=project_path,
    )


def parse_sessions_in_directory(directory: Path) -> list[ParsedSession]:
    """Parse all JSONL session files in a directory.

    Args:
        directory: Path to directory containing JSONL files.

    Returns:
        List of parsed sessions, sorted by start time (newest first).
    """
    sessions = []

    # Search recursively for JSONL files
    for jsonl_file in directory.glob("**/*.jsonl"):
        # Skip subagent files - they're nested sessions
        if "subagents" in str(jsonl_file):
            continue
        try:
            session = parse_session(jsonl_file)
            sessions.append(session)
        except Exception:
            # Skip files that can't be parsed
            continue

    # Sort by start time (newest first)
    sessions.sort(key=lambda s: s.start_time or "", reverse=True)
    return sessions
