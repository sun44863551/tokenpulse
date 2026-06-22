"""Bridge between the background pipeline and the Qt UI.

``AppController`` lives on the GUI thread and owns a ``Storage`` and a
``Pipeline``.  Callbacks from the worker thread are re-emitted as Qt
signals so widgets can update safely.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .core.config import SourceConfig, discover_sources, looks_like_interaction_plan
from .core.models import InteractionRecord, RateLimitSnapshot, UsageRecord
from .storage.db import Storage, Totals
from .watcher.file_watcher import Pipeline


class AppController(QObject):
    """Top-level controller that wires the pipeline to the UI."""

    new_usage = Signal(object)         # UsageRecord
    new_interaction = Signal(object)   # InteractionRecord
    sources_changed = Signal(list)     # list[SourceStatus]
    # Polled stats: a snapshot is emitted at ``refresh_interval`` so the UI
    # can paint aggregates without storing duplicate state.
    stats_updated = Signal(object, dict, object)  # Totals, dict[tool, Totals], RateLimitSnapshot
    interaction_plan_changed = Signal(bool, str)  # is_interaction_plan, plan_type

    def __init__(self, storage: Storage, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._storage = storage
        self._pipeline: Optional[Pipeline] = None
        self._sources: list[SourceConfig] = []
        self._interaction_plan = False
        self._interaction_plan_type: Optional[str] = None
        self._refresh = QTimer(self)
        self._refresh.setInterval(1000)
        self._refresh.timeout.connect(self._emit_stats)
        self._refresh.start()
        # Quota thresholds: (percent, cooldown seconds).
        self._quota_alerts = {70: 600, 90: 300}
        self._last_alert_ts: dict = {}

    # --------------------------------------------------------------- public
    def set_sources(self, sources: list[SourceConfig]) -> None:
        if sources == self._sources:
            return
        self.stop_pipeline()
        self._sources = sources
        self.start_pipeline()

    def sources(self) -> list[SourceConfig]:
        return list(self._sources)

    def start_pipeline(self) -> None:
        if self._pipeline is not None:
            return
        if not self._sources:
            return
        self._pipeline = Pipeline(
            self._sources,
            on_usage=self._handle_usage,
            on_interaction=self._handle_interaction,
        )
        self._pipeline.start()
        self._emit_sources()

    def stop_pipeline(self) -> None:
        if self._pipeline is not None:
            self._pipeline.stop()
            self._pipeline = None

    def storage(self) -> Storage:
        return self._storage

    def is_interaction_plan(self) -> bool:
        return self._interaction_plan

    def interaction_plan_type(self) -> Optional[str]:
        return self._interaction_plan_type

    # ------------------------------------------------------- internal slots
    def _handle_usage(self, record: UsageRecord) -> None:
        try:
            self._storage.upsert_usage(record)
        except Exception:
            return
        # Forward to UI via queued signal.
        self.new_usage.emit(record)
        self._update_plan_hint(record.plan_type)

    def _handle_interaction(self, record: InteractionRecord) -> None:
        try:
            self._storage.upsert_interaction(record)
        except Exception:
            return
        self.new_interaction.emit(record)
        self._update_plan_hint(record.plan_type)

    def _update_plan_hint(self, plan_type: Optional[str]) -> None:
        if not plan_type:
            return
        is_int = looks_like_interaction_plan(plan_type)
        if is_int != self._interaction_plan or plan_type != self._interaction_plan_type:
            self._interaction_plan = is_int
            self._interaction_plan_type = plan_type
            self.interaction_plan_changed.emit(is_int, plan_type or "")

    def _emit_sources(self) -> None:
        # Emit a SourceStatus list for the status bar.
        from .core.models import SourceStatus
        statuses = []
        for s in self._sources:
            file_count = 0
            for p in s.paths:
                if p.is_file():
                    file_count += 1
                elif p.is_dir():
                    for root, _, files in __import__("os").walk(p):
                        for f in files:
                            if f.endswith(".jsonl"):
                                file_count += 1
            statuses.append(
                SourceStatus(
                    tool=s.tool,
                    label=s.label,
                    paths=[str(x) for x in s.paths],
                    file_count=file_count,
                    active=True,
                )
            )
        self.sources_changed.emit(statuses)

    def _maybe_notify_quota(self, rate) -> None:
        """Show a desktop notification when the 5h quota crosses a threshold."""
        if rate is None or rate.primary_used_percent is None:
            return
        import time
        pct = rate.primary_used_percent
        tool = rate.tool
        for threshold, cooldown in sorted(self._quota_alerts.items()):
            if pct < threshold:
                continue
            key = (tool, threshold)
            last = self._last_alert_ts.get(key, 0)
            if time.time() - last < cooldown:
                continue
            self._last_alert_ts[key] = time.time()
            self._show_notification(
                "TokenPulse — %s 5小时配额" % tool,
                "已使用 %.0f%% 的 5 小时配额。" % pct,
            )

    def _show_notification(self, title: str, body: str) -> None:
        """Best-effort OS notification.  Falls back to a silent no-op."""
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            tray = QSystemTrayIcon.instance()
            if tray is not None:
                tray.showMessage(title, body, QSystemTrayIcon.Warning, 5000)
        except Exception:
            pass

    @Slot()
    def _emit_stats(self) -> None:
        totals = self._storage.totals()
        by_tool = self._storage.totals_by_tool()
        rate = self._storage.latest_rate_limit()
        self.stats_updated.emit(totals, by_tool, rate)
        self._maybe_notify_quota(rate)


def build_default_controller() -> AppController:
    """Create an AppController pointed at the local data dir."""
    from .core.config import db_path
    storage = Storage(db_path())
    controller = AppController(storage)
    sources = discover_sources()
    controller.set_sources(sources)
    return controller