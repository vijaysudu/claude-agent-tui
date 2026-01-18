"""File watcher for Claude session JSONL files."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class SessionWatcher:
    """Watches for new and modified Claude session files."""

    def __init__(
        self,
        directory: Path,
        on_change: Callable[[Path], None] | None = None,
        on_new: Callable[[Path], None] | None = None,
    ):
        """Initialize the session watcher.

        Args:
            directory: Directory to watch for JSONL files.
            on_change: Callback when a file is modified.
            on_new: Callback when a new file is created.
        """
        self.directory = directory
        self.on_change = on_change
        self.on_new = on_new
        self._observer: Observer | None = None

    def start(self) -> None:
        """Start watching for file changes."""
        handler = _SessionEventHandler(self.on_change, self.on_new)
        self._observer = Observer()
        # Watch recursively since sessions are in project subdirectories
        self._observer.schedule(handler, str(self.directory), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        """Stop watching for file changes."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None


class _SessionEventHandler(FileSystemEventHandler):
    """Handles file system events for session files."""

    def __init__(
        self,
        on_change: Callable[[Path], None] | None,
        on_new: Callable[[Path], None] | None,
    ):
        self.on_change = on_change
        self.on_new = on_new

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix == ".jsonl" and self.on_change:
            self.on_change(path)

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix == ".jsonl" and self.on_new:
            self.on_new(path)
