"""File watcher for Claude Code session files.

Watches for changes to session files and notifies callbacks.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

from watchfiles import awatch, Change

from ..logging import get_logger
from .scanner import CLAUDE_PROJECTS_DIR, SessionInfo, scan_sessions

log = get_logger("watcher")


class SessionWatcher:
    """Watches for changes to Claude Code session files.

    Uses watchfiles (based on Rust's notify) for efficient file system monitoring.
    """

    def __init__(
        self,
        projects_dir: Path | None = None,
        on_session_change: Callable[[SessionInfo], None] | None = None,
        on_new_session: Callable[[SessionInfo], None] | None = None,
    ) -> None:
        """Initialize the session watcher.

        Args:
            projects_dir: Directory to watch. Defaults to ~/.claude/projects/
            on_session_change: Callback when a session file is modified
            on_new_session: Callback when a new session file is created
        """
        self.projects_dir = projects_dir or CLAUDE_PROJECTS_DIR
        self.on_session_change = on_session_change
        self.on_new_session = on_new_session
        self._running = False
        self._watch_task: asyncio.Task | None = None
        self._known_sessions: set[str] = set()

    async def start(self) -> None:
        """Start watching for session file changes."""
        if self._running:
            return

        if not self.projects_dir.exists():
            log.warning(f"Projects directory does not exist: {self.projects_dir}")
            return

        # Initialize known sessions
        existing = scan_sessions(self.projects_dir)
        self._known_sessions = {s.session_id for s in existing}

        self._running = True
        self._watch_task = asyncio.create_task(self._watch_loop())
        log.info(f"Started watching {self.projects_dir}")

    async def stop(self) -> None:
        """Stop watching for changes."""
        self._running = False
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None
        log.info("Stopped watching")

    async def _watch_loop(self) -> None:
        """Main watch loop."""
        try:
            async for changes in awatch(
                self.projects_dir,
                recursive=True,
                step=500,  # Check every 500ms
            ):
                if not self._running:
                    break

                for change_type, path_str in changes:
                    path = Path(path_str)

                    # Only care about JSONL files
                    if path.suffix != ".jsonl":
                        continue

                    session_id = path.stem
                    encoded_cwd = path.parent.name

                    try:
                        stat = path.stat()
                        from datetime import datetime
                        from .scanner import decode_cwd

                        session_info = SessionInfo(
                            session_id=session_id,
                            cwd=decode_cwd(encoded_cwd),
                            file_path=path,
                            last_modified=datetime.fromtimestamp(stat.st_mtime),
                            file_size=stat.st_size,
                            encoded_cwd=encoded_cwd,
                        )
                    except OSError:
                        continue

                    if change_type == Change.added:
                        if session_id not in self._known_sessions:
                            self._known_sessions.add(session_id)
                            log.debug(f"New session: {session_id}")
                            if self.on_new_session:
                                self.on_new_session(session_info)

                    elif change_type == Change.modified:
                        log.debug(f"Session modified: {session_id}")
                        if self.on_session_change:
                            self.on_session_change(session_info)

                    elif change_type == Change.deleted:
                        self._known_sessions.discard(session_id)
                        log.debug(f"Session deleted: {session_id}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Watch loop error: {e}")
            raise

    @property
    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self._running


async def watch_sessions(
    on_change: Callable[[SessionInfo], None],
    on_new: Callable[[SessionInfo], None] | None = None,
    projects_dir: Path | None = None,
) -> SessionWatcher:
    """Create and start a session watcher.

    Convenience function to create and start a watcher.

    Args:
        on_change: Callback for session changes
        on_new: Callback for new sessions (optional)
        projects_dir: Directory to watch

    Returns:
        Running SessionWatcher instance
    """
    watcher = SessionWatcher(
        projects_dir=projects_dir,
        on_session_change=on_change,
        on_new_session=on_new,
    )
    await watcher.start()
    return watcher
