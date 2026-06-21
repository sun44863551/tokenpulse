"""Reusable chart widgets built on pyqtgraph."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Optional

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget


# pyqtgraph uses Qt's rendering pipeline.  We force a dark, high-DPI
# style that matches the rest of the app.
pg.setConfigOption("background", "#0d1117")
pg.setConfigOption("foreground", "#e6edf3")
pg.setConfigOption("antialias", True)


class TimeSeriesChart(QWidget):
    """A live line chart of tokens-per-minute per tool."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.plot = pg.PlotWidget(title="")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("left", "Tokens")
        self.plot.setLabel("bottom", "Time")
        self.plot.getPlotItem().setMenuEnabled(False)
        self.plot.setMouseEnabled(x=True, y=False)
        layout.addWidget(self.plot)

        self._curves: dict[str, pg.PlotDataItem] = {}
        self._buckets: dict[str, Deque[tuple[float, float]]] = defaultdict(
            lambda: deque(maxlen=240)  # 4 hours at 1-minute buckets
        )
        self._colors = {
            "codex": "#2f81f7",
            "claude-code": "#a371f7",
            "total": "#39d353",
        }
        legend = self.plot.addLegend(offset=(10, 10))
        legend.setBrush("#161b22")
        legend.setPen("#30363d")

    def add_point(self, tool: str, ts_ms: int, value: float) -> None:
        bucket_ts = (ts_ms // 60_000) * 60  # minute bucket
        buckets = self._buckets[tool]
        if buckets and buckets[-1][0] == bucket_ts:
            # Accumulate inside the current minute.
            last_ts, last_v = buckets[-1]
            buckets[-1] = (last_ts, last_v + value)
        else:
            buckets.append((bucket_ts, value))
        self._refresh_curve(tool)

    def _refresh_curve(self, tool: str) -> None:
        buckets = self._buckets[tool]
        if not buckets:
            return
        xs = [b[0] for b in buckets]
        ys = [b[1] for b in buckets]
        if tool not in self._curves:
            color = self._colors.get(tool, "#e6edf3")
            self._curves[tool] = self.plot.plot(
                xs,
                ys,
                pen=pg.mkPen(color=color, width=2),
                name=tool,
                symbol=None,
            )
        else:
            self._curves[tool].setData(xs, ys)


class TokenBreakdownBar(QWidget):
    """Stacked horizontal bar showing input/output/cache_read/cache_write/thinking."""

    COLORS = {
        "input": "#2f81f7",
        "output": "#39d353",
        "cache_read": "#a371f7",
        "cache_write": "#d29922",
        "thinking": "#f78166",
    }
    LABELS = {
        "input": "Input",
        "output": "Output",
        "cache_read": "Cache read",
        "cache_write": "Cache write",
        "thinking": "Thinking",
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.PlotWidget()
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()
        self.plot.getPlotItem().setMenuEnabled(False)
        self.plot.setBackground("#161b22")
        layout.addWidget(self.plot)


        self._bars: dict[str, pg.BarGraphItem] = {}
        self._labels: list[str] = []
        self._ticklabels: list[pg.TextItem] = []

    def set_data(self, totals: dict[str, dict[str, int]]) -> None:
        """``totals`` maps category -> {tool: tokens}."""
        self.plot.clear()
        if not totals:
            return
        tools = sorted({t for v in totals.values() for t in v})
        y_positions = list(range(len(tools)))
        self._labels = tools
        self.plot.getAxis("left").setTicks([list(zip(y_positions, tools))])

        left = [0] * len(tools)
        for cat in ("input", "output", "cache_read", "cache_write", "thinking"):
            ys: list[float] = []
            hs: list[float] = []
            bs: list[float] = []
            for idx, tool in enumerate(tools):
                v = totals.get(cat, {}).get(tool, 0)
                ys.append(idx)
                hs.append(max(0.3, v / max(1, sum(totals[c].get(tool, 0) for c in totals))))
                bs.append(left[idx])
                left[idx] += v
            if not any(bs):
                continue
            bar = pg.BarGraphItem(
                x0=bs,
                y=ys,
                height=0.6,
                width=[b - a for a, b in zip(bs, [bs[i] + (totals[cat].get(tools[i], 0)) for i in range(len(tools))])],
                brush=self.COLORS[cat],
                pen=None,
            )
            self.plot.addItem(bar)
        # Right-edge labels with totals.
        for idx, tool in enumerate(tools):
            total = sum(cat.get(tool, 0) for cat in totals.values())
            label = pg.TextItem(
                text=f"{total:,}", color="#e6edf3", anchor=(0, 0.5)
            )
            label.setPos(left[idx], idx)
            self.plot.addItem(label)