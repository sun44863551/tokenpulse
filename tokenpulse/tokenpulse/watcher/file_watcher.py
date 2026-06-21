"""Pipeline that watches log files and dispatches parsed events to a callback.

The pipeline is plain Python (no Qt) so it can run inside a worker
thread.  ``AppController`` (in ``app.py``) bridges the callback to Qt
signals on the GUI thread.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..core.config import SourceConfig
from ..core.models import InteractionRecord, UsageRecord
from ..parsers import get_parser
from ..parsers.base import ParseContext, ParseEvent


def process_file(path: Path, tool: str, on_event: Callable[[ParseEvent], None]) -> None:
    """Parse a JSONL file from start to end and emit events."""
    parser = get_parser(tool)
    if parser is None:
        return
    context: ParseContext = parser.new_context(str(path))
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line_offset, raw in enumerate(fh, start=1):
                for event in parser.feed(raw, context, line_offset):
                    on_event(event)
            # Capture final offset for live tailing.
            context._final_offset = fh.tell()  # type: ignore[attr-defined]
    except OSError:
        return
    for event in parser.finalize(context):
        on_event(event)


class _FileState:
    __slots__ = ("path", "context", "last_offset", "missing")

    def __init__(self, path: Path, context: ParseContext):
        self.path = path
        self.context = context
        self.last_offset = 0
        self.missing = False


class _DirHandler(FileSystemEventHandler):
    def __init__(self, pipeline: "Pipeline"):
        self._pipeline = pipeline

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._pipeline._handle_path(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._pipeline._handle_path(Path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._pipeline._handle_path(Path(event.dest_path))


class Pipeline:
    """Watch one or more log directories and stream events to a callback.

    Lifecycle:

    >>> pipeline = Pipeline([source_config_a, source_config_b], callback)
    >>> pipeline.start()
    ... # it runs in a worker thread until stop() is called
    >>> pipeline.stop()
    """

    def __init__(
        self,
        sources: list[SourceConfig],
        on_usage: Callable[[UsageRecord], None],
        on_interaction: Callable[[InteractionRecord], None],
        poll_interval: float = 0.5,
    ):
        self._sources = {s.tool: s for s in sources}
        self._on_usage = on_usage
        self._on_interaction = on_interaction
        self._poll = poll_interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._observer: Optional[Observer] = None
        self._lock = threading.RLock()
        # Per-tool file state for live tailing.
        self._states: dict[tuple[str, Path], _FileState] = {}

    # ----------------------------------------------------------- public API
    def start(self) -> None:
        if self._thread is not None:
            return
        # Start the watchdog observer (best effort).
        try:
            observer = Observer()
            for source in self._sources.values():
                for path in source.paths:
                    if path.exists():
                        observer.schedule(
                            _DirHandler(self), str(path), recursive=True
                        )
            observer.daemon = True
            observer.start()
            self._observer = observer
        except Exception:
            # Watchdog can fail on locked-down Windows containers; we still
            # want the polling loop to work.
            self._observer = None
        self._thread = threading.Thread(
            target=self._run, name="TokenPulse-Pipeline", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=2.0)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=3.0)

    # ----------------------------------------------------- internal helpers
    def _initial_scan(self, source: SourceConfig) -> None:
        for directory in source.paths:
            if not directory.exists():
                continue
            for root, _, files in os.walk(directory):
                for name in files:
                    if not name.endswith(".jsonl"):
                        continue
                    path = Path(root) / name
                    self._process_full(path, source.tool)

    def _process_full(self, path: Path, tool: str) -> None:
        """Parse a file from offset 0, then record the offset for live tailing."""
        parser = get_parser(tool)
        if parser is None:
            return
        context: ParseContext = parser.new_context(str(path))
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for line_offset, raw in enumerate(fh, start=1):
                    for event in parser.feed(raw, context, line_offset):
                        self._dispatch(event)
                offset = fh.tell()
        except OSError:
            return
        for event in parser.finalize(context):
            self._dispatch(event)
        with self._lock:
            self._states[(tool, path)] = _FileState(path, context)
            self._states[(tool, path)].last_offset = offset

    def _handle_path(self, path: Path) -> None:
        """Called by watchdog on file events."""
        if path.suffix != ".jsonl":
            return
        # Find which tool owns this path.
        for tool, source in self._sources.items():
            if any(self._is_under(path, root) for root in source.paths):
                with self._lock:
                    key = (tool, path)
                    if key not in self._states:
                        # New file: parse it fully.
                        self._process_full(path, tool)
                    else:
                        # Existing file: tail the new bytes.
                        self._tail_file(tool, path)
                return

    @staticmethod
    def _is_under(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def _tail_file(self, tool: str, path: Path) -> None:
        with self._lock:
            state = self._states.get((tool, path))
            if state is None:
                return
            try:
                size = path.stat().st_size
            except OSError:
                return
            if size < state.last_offset:
                # Rotated/truncated.  Re-parse from scratch.
                self._process_full(path, tool)
                return
            if size == state.last_offset:
                return
            try:
                with path.open("rb") as fh:
                    fh.seek(state.last_offset)
                    chunk = fh.read(size - state.last_offset)
            except OSError:
                return
            state.last_offset = size
        # Parse the new bytes.  Split lines outside the lock for speed.
        text = chunk.decode("utf-8", errors="replace")
        parser = get_parser(tool)
        if parser is None:
            return
        for raw in text.splitlines():
            for event in parser.feed(raw, state.context, 0):
                self._dispatch(event)

    def _dispatch(self, event: ParseEvent) -> None:
        if event.usage is not None:
            try:
                self._on_usage(event.usage)
            except Exception:
                pass
        if event.interaction is not None:
            try:
                self._on_interaction(event.interaction)
            except Exception:
                pass

    def _run(self) -> None:
        """Worker loop: do an initial scan, then poll-tracks live changes."""
        # Initial scan first so the dashboard has data immediately.
        for source in self._sources.values():
            try:
                self._initial_scan(source)
            except Exception:
                pass
        # Then enter the poll loop.
        while not self._stop.is_set():
            with self._lock:
                states = list(self._states.values())
            for state in states:
                self._tail_file_for_state(state)
            self._stop.wait(self._poll)

    def _tail_file_for_state(self, state: _FileState) -> None:
        # Find the tool for this state by matching its path.
        tool: Optional[str] = None
        for t, source in self._sources.items():
            if any(self._is_under(state.path, root) for root in source.paths):
                tool = t
                break
        if tool is None:
            return
        self._tail_file(tool, state.path)
