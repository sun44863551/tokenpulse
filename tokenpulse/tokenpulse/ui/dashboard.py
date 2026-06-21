"""The main dashboard widget.  Owns the layout, chart, and KPI cards."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..app import AppController
from ..core.models import RateLimitSnapshot, SourceStatus
from ..storage.db import Totals
from .charts import TimeSeriesChart, TokenBreakdownBar


def _humanize(n: int) -> str:
    n = float(n)
    for unit in ("", "K", "M", "B", "T"):
        if abs(n) < 1000.0:
            return f"{n:,.1f}{unit}".replace(".0", "")
        n /= 1000.0
    return f"{n:,.1f}P"


def _format_money(amount: float) -> str:
    if amount >= 1:
        return f"${amount:,.2f}"
    if amount >= 0.01:
        return f"${amount:.3f}"
    return f"${amount:.4f}"


def _format_eta(ts_ms: Optional[int]) -> str:
    if not ts_ms:
        return "—"
    delta_s = (ts_ms / 1000.0) - datetime.now().timestamp()
    if delta_s <= 0:
        return "now"
    if delta_s < 60:
        return f"in {int(delta_s)}s"
    if delta_s < 3600:
        return f"in {int(delta_s // 60)}m"
    if delta_s < 86400:
        return f"in {delta_s / 3600:.1f}h"
    return f"in {delta_s / 86400:.1f}d"


def _format_time(ts_ms: int) -> str:
    if not ts_ms:
        return "—"
    return datetime.fromtimestamp(ts_ms / 1000.0).strftime("%H:%M:%S")


class _Card(QFrame):
    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        self.value_label = QLabel("—")
        self.value_label.setObjectName("cardValue")
        self.sub_label = QLabel("")
        self.sub_label.setObjectName("cardSubValue")
        self.sub_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.sub_label)


class Dashboard(QWidget):
    def __init__(self, controller: AppController, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("root")
        self._controller = controller
        self._interaction_plan = False
        self._plan_type: Optional[str] = None

        # Top KPI row
        self.total_card = _Card("Total tokens")
        self.cost_card = _Card("Estimated cost")
        self.interactions_card = _Card("Interactions")
        self.interactions_card.sub_label.setText("Subscription turns")

        # Right side: per-tool breakdown cards
        self.tool_box = QVBoxLayout()
        self.tool_box.setContentsMargins(0, 0, 0, 0)
        self.tool_box.setSpacing(10)
        self.tool_holder = QWidget()
        self.tool_holder.setLayout(self.tool_box)
        self.tool_scroll = QScrollArea()
        self.tool_scroll.setWidgetResizable(True)
        self.tool_scroll.setWidget(self.tool_holder)
        self.tool_scroll.setFrameShape(QFrame.NoFrame)
        self._tool_cards: dict[str, dict[str, QLabel]] = {}

        # Charts
        self.chart = TimeSeriesChart()
        self.breakdown = TokenBreakdownBar()

        # Recent activity
        self.recent = QListWidget()
        self.recent.setMinimumHeight(160)

        self._build_layout()

        # Connect signals.
        controller.new_usage.connect(self._on_new_usage)
        controller.new_interaction.connect(self._on_new_interaction)
        controller.stats_updated.connect(self._on_stats_updated)
        controller.interaction_plan_changed.connect(self._on_plan_changed)
        controller.sources_changed.connect(self._on_sources_changed)

        # Trigger an initial paint from current storage contents and the
        # controller's known sources.  The ``sources_changed`` signal may
        # have fired before this widget existed, so we replay it now.
        self._sync_sources_from_controller()
        self._refresh_totals_from_storage()

    # ---------------------------------------------------------------- layout
    def _build_layout(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        # Header row.
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("TokenPulse")
        title.setObjectName("titleLabel")
        subtitle = QLabel("Real-time token usage for Codex, Claude Code, and friends")
        subtitle.setObjectName("subtitleLabel")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self.plan_pill = QLabel("Detecting…")
        self.plan_pill.setObjectName("pill")
        self.plan_pill.setVisible(False)
        header.addWidget(self.plan_pill, 0, Qt.AlignRight)
        self.refresh_button = QPushButton("Refresh now")
        self.refresh_button.clicked.connect(self._refresh_totals_from_storage)
        header.addWidget(self.refresh_button, 0, Qt.AlignRight)
        outer.addLayout(header)

        # KPI grid (responsive).
        kpi_row = QGridLayout()
        kpi_row.setSpacing(10)
        kpi_row.addWidget(self.total_card, 0, 0)
        kpi_row.addWidget(self.cost_card, 0, 1)
        kpi_row.addWidget(self.interactions_card, 0, 2)
        # Allow the cards to grow with the window.
        for col in range(3):
            kpi_row.setColumnStretch(col, 1)
        outer.addLayout(kpi_row)

        # Main row: chart on the left, tool breakdown on the right.
        main_row = QHBoxLayout()
        main_row.setSpacing(14)
        chart_card = QFrame()
        chart_card.setObjectName("card")
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(14, 12, 14, 12)
        chart_title = QLabel("Tokens per minute (live)")
        chart_title.setObjectName("cardTitle")
        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(self.chart)
        main_row.addWidget(chart_card, stretch=3)

        tools_card = QFrame()
        tools_card.setObjectName("card")
        tools_layout = QVBoxLayout(tools_card)
        tools_layout.setContentsMargins(14, 12, 14, 12)
        tools_title = QLabel("Per-tool")
        tools_title.setObjectName("cardTitle")
        tools_layout.addWidget(tools_title)
        tools_layout.addWidget(self.tool_scroll)
        main_row.addWidget(tools_card, stretch=2)
        outer.addLayout(main_row, stretch=3)

        # Breakdown + recent.
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(14)
        breakdown_card = QFrame()
        breakdown_card.setObjectName("card")
        breakdown_layout = QVBoxLayout(breakdown_card)
        breakdown_layout.setContentsMargins(14, 12, 14, 12)
        bd_title = QLabel("Token breakdown by tool")
        bd_title.setObjectName("cardTitle")
        breakdown_layout.addWidget(bd_title)
        breakdown_layout.addWidget(self.breakdown)
        bottom_row.addWidget(breakdown_card, stretch=3)

        recent_card = QFrame()
        recent_card.setObjectName("card")
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(14, 12, 14, 12)
        r_title = QLabel("Recent activity")
        r_title.setObjectName("cardTitle")
        recent_layout.addWidget(r_title)
        recent_layout.addWidget(self.recent)
        bottom_row.addWidget(recent_card, stretch=2)
        outer.addLayout(bottom_row, stretch=2)

    # ------------------------------------------------------------------ slots
    @Slot(object)
    def _on_new_usage(self, record) -> None:
        # Push a point into the per-minute chart.
        self.chart.add_point(record.tool, record.ts, record.total_tokens)
        # Prepend a recent-activity item.
        item_text = (
            f"{_format_time(record.ts)}  ?  {record.tool}  ?  "
            f"{record.model or '?'}  ?  {_humanize(record.total_tokens)} tokens"
        )
        li = QListWidgetItem(item_text)
        self.recent.insertItem(0, li)
        if self.recent.count() > 50:
            self.recent.takeItem(self.recent.count() - 1)

    @Slot(object)
    def _on_new_interaction(self, record) -> None:
        # Refresh interaction counter immediately.
        totals = self._controller.storage().totals()
        self.interactions_card.value_label.setText(f"{totals.interactions:,}")

    @Slot(object, dict, object)
    def _on_stats_updated(self, totals: Totals, by_tool: dict, rate) -> None:
        self._render_totals(totals, by_tool, rate)

    @Slot(bool, str)
    def _on_plan_changed(self, is_interaction_plan: bool, plan_type: str) -> None:
        self._interaction_plan = is_interaction_plan
        self._plan_type = plan_type or None
        self._update_plan_pill()
        # Also adjust the interactions card title to reflect the billing mode.
        if is_interaction_plan:
            self.interactions_card.title_label.setText("Turns (token plan)")
            self.interactions_card.sub_label.setText(
                f"Subscription plan \"{plan_type}\" — each user turn counts as one interaction."
            )
        else:
            self.interactions_card.title_label.setText("User turns")
            self.interactions_card.sub_label.setText(
                "Turns detected from local session logs."
            )

    @Slot(list)
    def _on_sources_changed(self, sources) -> None:
        # Render per-tool cards for each known source.
        existing = set(self._tool_cards.keys())
        seen = set()
        for source in sources:
            self._ensure_tool_card(source)
            seen.add(source.tool)
        for tool in list(self._tool_cards.keys()):
            if tool not in seen:
                # Remove card.
                w = self._tool_cards.pop(tool)
                w["frame"].setParent(None)
                w["frame"].deleteLater()
        # Force a repaint of totals so per-card values are populated.
        self._refresh_totals_from_storage()

    # ----------------------------------------------------------------- render
    def _ensure_tool_card(self, source: SourceStatus) -> None:
        if source.tool in self._tool_cards:
            return
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        title = QLabel(source.label)
        title.setObjectName("cardTitle")
        value = QLabel("0")
        value.setObjectName("cardValue")
        sub = QLabel(f"{source.file_count} files")
        sub.setObjectName("cardSubValue")
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(sub)

        # Per-tool rate-limit bar (Codex-style).
        rate_bar = QProgressBar()
        rate_bar.setRange(0, 100)
        rate_bar.setValue(0)
        rate_bar.setFormat("%p% 5h")
        rate_bar.setObjectName("ratePrimary")
        layout.addWidget(rate_bar)

        rate_bar_secondary = QProgressBar()
        rate_bar_secondary.setRange(0, 100)
        rate_bar_secondary.setValue(0)
        rate_bar_secondary.setFormat("%p% weekly")
        rate_bar_secondary.setObjectName("rateSecondary")
        layout.addWidget(rate_bar_secondary)

        self.tool_box.addWidget(frame)
        self._tool_cards[source.tool] = {
            "frame": frame,
            "title": title,
            "value": value,
            "sub": sub,
            "rate_primary": rate_bar,
            "rate_secondary": rate_bar_secondary,
            "label": source.label,
        }

    def _render_totals(self, totals: Totals, by_tool: dict, rate) -> None:
        self.total_card.value_label.setText(_humanize(totals.total_tokens))
        self.total_card.sub_label.setText(
            f"{totals.records:,} record(s) ? "
            f"In {_humanize(totals.input_tokens)} · Out {_humanize(totals.output_tokens)}"
        )
        self.cost_card.value_label.setText(_format_money(totals.cost))
        self.cost_card.sub_label.setText(
            "Computed from public list prices ? cache reads discounted"
        )
        self.interactions_card.value_label.setText(f"{totals.interactions:,}")

        # Per-tool cards.
        for tool, t in by_tool.items():
            card = self._tool_cards.get(tool)
            if card is None:
                continue
            card["value"].setText(_humanize(t.total_tokens))
            card["sub"].setText(
                f"{t.records:,} recs ? In {_humanize(t.input_tokens)} · "
                f"Out {_humanize(t.output_tokens)} ? {_format_money(t.cost)}"
            )

        # Codex rate-limit bar.
        if rate is not None and rate.tool in self._tool_cards:
            card = self._tool_cards[rate.tool]
            primary = rate.primary_used_percent or 0
            secondary = rate.secondary_used_percent or 0
            card["rate_primary"].setValue(int(primary))
            card["rate_primary"].setFormat(
                f"{primary:.0f}% 5h  ?  reset {_format_eta(rate.primary_resets_at)}"
            )
            if primary >= 90:
                card["rate_primary"].setObjectName("danger")
            elif primary >= 70:
                card["rate_primary"].setObjectName("warning")
            else:
                card["rate_primary"].setObjectName("ratePrimary")
            card["rate_primary"].style().unpolish(card["rate_primary"])
            card["rate_primary"].style().polish(card["rate_primary"])

            card["rate_secondary"].setValue(int(secondary))
            card["rate_secondary"].setFormat(
                f"{secondary:.0f}% wk  ?  reset {_format_eta(rate.secondary_resets_at)}"
            )
            if secondary >= 90:
                card["rate_secondary"].setObjectName("danger")
            elif secondary >= 70:
                card["rate_secondary"].setObjectName("warning")
            else:
                card["rate_secondary"].setObjectName("rateSecondary")
            card["rate_secondary"].style().unpolish(card["rate_secondary"])
            card["rate_secondary"].style().polish(card["rate_secondary"])

        # Stacked bar across tools.
        breakdown: dict[str, dict[str, int]] = {
            "input": {},
            "output": {},
            "cache_read": {},
            "cache_write": {},
            "thinking": {},
        }
        # Use totals aggregated across the storage.
        # For a per-tool breakdown we need to read each tool's breakdown
        # from the storage; do a single query.
        per_tool_breakdown = self._controller.storage().breakdown_by_tool()
        for tool, cats in per_tool_breakdown.items():
            for cat in breakdown:
                breakdown[cat][tool] = cats.get(cat, 0)
        self.breakdown.set_data(breakdown)

    def _update_plan_pill(self) -> None:
        if not self._plan_type:
            self.plan_pill.setVisible(False)
            return
        self.plan_pill.setVisible(True)
        if self._interaction_plan:
            self.plan_pill.setText(f"Plan: {self._plan_type}  ?  counting turns")
            self.plan_pill.setObjectName("pillSuccess")
        else:
            self.plan_pill.setText(f"Plan: {self._plan_type}  ?  counting tokens")
            self.plan_pill.setObjectName("pill")
        self.plan_pill.style().unpolish(self.plan_pill)
        self.plan_pill.style().polish(self.plan_pill)

    def _refresh_totals_from_storage(self) -> None:
        storage = self._controller.storage()
        totals = storage.totals()
        by_tool = storage.totals_by_tool()
        rate = storage.latest_rate_limit()
        self._render_totals(totals, by_tool, rate)
        # Plan pill state.
        if rate and rate.plan_type:
            self._on_plan_changed(
                self._controller.is_interaction_plan(),
                rate.plan_type,
            )
    def _sync_sources_from_controller(self) -> None:
        """Build per-tool cards for every source the controller knows about."""
        from ..core.models import SourceStatus
        statuses = []
        for s in self._controller.sources():
            file_count = 0
            for p in s.paths:
                if p.is_file():
                    file_count += 1
                elif p.is_dir():
                    import os
                    for root, _, files in os.walk(p):
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
        self._on_sources_changed(statuses)
