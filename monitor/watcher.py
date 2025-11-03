"""
File watcher for Claude Code history.jsonl
"""

import json
import time
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from monitor.models import ClaudeHistoryEvent


class HistoryWatcher(FileSystemEventHandler):
    """Watches Claude Code history file for new events."""

    def __init__(
        self,
        history_path: Path,
        on_new_event: Callable[[ClaudeHistoryEvent], None],
    ):
        self.history_path = history_path
        self.on_new_event = on_new_event
        self.last_position = 0
        self._initialize_position()

    def _initialize_position(self) -> None:
        """Set initial file position to end of file."""
        if self.history_path.exists():
            with open(self.history_path, "rb") as f:
                f.seek(0, 2)  # Seek to end
                self.last_position = f.tell()

    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modification events."""
        if event.src_path != str(self.history_path):
            return

        self._read_new_entries()

    def _read_new_entries(self) -> None:
        """Read and parse new entries from the history file."""
        if not self.history_path.exists():
            return

        with open(self.history_path, "r", encoding="utf-8") as f:
            f.seek(self.last_position)
            new_lines = f.readlines()
            self.last_position = f.tell()

        for line in new_lines:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                event = ClaudeHistoryEvent(**data)
                self.on_new_event(event)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing history entry: {e}")
                continue

    def force_check(self) -> None:
        """Manually check for new entries (for polling mode)."""
        self._read_new_entries()


class HistoryMonitor:
    """High-level interface for monitoring Claude Code history."""

    def __init__(
        self,
        history_path: str,
        on_new_event: Callable[[ClaudeHistoryEvent], None],
        poll_interval: float = 1.0,
    ):
        self.history_path = Path(history_path).expanduser()
        self.watcher = HistoryWatcher(self.history_path, on_new_event)
        self.observer: Optional[Observer] = None
        self.poll_interval = poll_interval
        self._running = False

    def start(self, use_polling: bool = False) -> None:
        """Start monitoring the history file."""
        self._running = True

        if use_polling:
            self._run_polling_mode()
        else:
            self._run_observer_mode()

    def _run_observer_mode(self) -> None:
        """Use watchdog observer for file system events."""
        self.observer = Observer()
        self.observer.schedule(
            self.watcher,
            str(self.history_path.parent),
            recursive=False,
        )
        self.observer.start()

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def _run_polling_mode(self) -> None:
        """Poll the file periodically for changes."""
        try:
            while self._running:
                self.watcher.force_check()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self.observer:
            self.observer.stop()
            self.observer.join()
