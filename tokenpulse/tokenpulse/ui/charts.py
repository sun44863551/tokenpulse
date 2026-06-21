"""Reusable chart widgets built on pyqtgraph."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Optional

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter
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

# ---------------------------------------------------------------- palette
_PALETTE = [
    "#2f81f7",  # blue
    "#a371f7",  # purple
    "#39d353",  # green
    "#d29922",  # amber
    "#f78166",  # orange
    "#db61a2",  # pink
    "#58a6ff",  # light blue
    "#7ee787",  # light green
    "#ff7b72",  # red
    "#bc8cff",  # lavender
]


def _color_for(label: str) -> str:
    return _PALETTE[hash(label) % len(_PALETTE)]


def _humanize(n) -> str:
    n = float(n)
    for unit, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if abs(n) >= unit:
            return f"{n / unit:,.1f}{suffix}".replace(".0", "")
    return f"{n:,.0f}"


class ModelPieChart(QWidget):
    """Donut/pie chart of total tokens by model (across all tools)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = pg.GraphicsView()
        self.view.setBackground("#161b22")
        self.view.setRenderHint(QPainter.Antialiasing, True)
        layout.addWidget(self.view, stretch=1)
        self._items: list = []
        self._labels: list[pg.TextItem] = []

    def set_data(self, model_totals: dict) -> None:
        # Reset scene.
        for it in self._items:
            self.view.removeItem(it)
        for lbl in self._labels:
            self.view.removeItem(lbl)
        self._items.clear()
        self._labels.clear()

        # Filter out tiny slices; combine into "Other".
        items = sorted(model_totals.items(), key=lambda kv: -kv[1])
        if not items:
            return
        total = sum(v for _, v in items)
        if total == 0:
            return
        threshold = total * 0.02
        main = [(k, v) for k, v in items if v >= threshold]
        other = sum(v for k, v in items if v < threshold)
        if other > 0:
            main.append(("Other", other))

        import math
        w = max(self.view.width(), 320)
        h = max(self.view.height(), 220)
        cx, cy = w / 2, h / 2 + 6
        radius = min(w, h) * 0.36
        inner = radius * 0.55

        start_angle = -math.pi / 2  # 12 o'clock
        for label, value in main:
            sweep = 2 * math.pi * (value / total)
            color = _color_for(label)
            path_item = _make_donut_slice(cx, cy, radius, inner, start_angle, start_angle + sweep, color)
            self.view.addItem(path_item)
            self._items.append(path_item)
            mid = start_angle + sweep / 2
            lx = cx + (radius * 0.78) * math.cos(mid)
            ly = cy + (radius * 0.78) * math.sin(mid)
            pct = value / total * 100
            text = "%s  %.0f%%" % (label, pct)
            t = pg.TextItem(text=text, color="#e6edf3", anchor=(0.5, 0.5))
            t.setPos(lx, ly)
            self.view.addItem(t)
            self._labels.append(t)
            start_angle += sweep

        # Center label: total.
        total_text = pg.TextItem(
            text="%s\ntokens" % _humanize(total),
            color="#f0f6fc", anchor=(0.5, 0.5),
        )
        f = QFont("", 11)
        f.setBold(True)
        total_text.setFont(f)
        total_text.setPos(cx, cy - 6)
        self.view.addItem(total_text)
        self._labels.append(total_text)


def _make_donut_slice(cx, cy, r_outer, r_inner, a0, a1, color):
    """Build a QGraphicsPathItem that draws a donut slice between angles a0..a1."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPainterPath, QPen, QBrush
    from PySide6.QtWidgets import QGraphicsPathItem
    import math
    path = QPainterPath()
    p0 = QPointF(cx + r_outer * math.cos(a0), cy + r_outer * math.sin(a0))
    p1 = QPointF(cx + r_outer * math.cos(a1), cy + r_outer * math.sin(a1))
    path.moveTo(p0)
    steps = max(8, int((a1 - a0) / (2 * math.pi) * 64))
    for i in range(1, steps + 1):
        a = a0 + (a1 - a0) * i / steps
        p = QPointF(cx + r_outer * math.cos(a), cy + r_outer * math.sin(a))
        path.lineTo(p)
    for i in range(steps, -1, -1):
        a = a0 + (a1 - a0) * i / steps
        p = QPointF(cx + r_inner * math.cos(a), cy + r_inner * math.sin(a))
        path.lineTo(p)
    path.closeSubpath()
    item = QGraphicsPathItem(path)
    item.setBrush(QBrush(QColor(color)))
    item.setPen(QPen(QColor("#0d1117"), 1))
    return item


class DailyHeatmap(QWidget):
    """A 7-day x 24-hour heatmap of token usage.

    Rows: weekday (Mon..Sun).  Cols: hour of day.  Cell intensity =
    relative token volume.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.PlotWidget()
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()
        self.plot.getPlotItem().setMenuEnabled(False)
        self.plot.setBackground("#161b22")
        self.plot.setAspectLocked(lock=True, ratio=1.0)
        layout.addWidget(self.plot)

        self._img = None
        self._colorbar = None

    def set_data(self, ts_values: list) -> None:
        """``ts_values`` is a list of (ts_ms, tokens) pairs."""
        if self._img is not None:
            self.plot.removeItem(self._img)
            self._img = None
        if self._colorbar is not None:
            self.plot.removeItem(self._colorbar)
            self._colorbar = None
        import numpy as np
        from datetime import datetime, timedelta
        grid = np.zeros((7, 24), dtype=float)
        now = datetime.now()
        start_of_today = datetime(now.year, now.month, now.day)
        earliest = start_of_today - timedelta(days=6)
        for ts_ms, value in ts_values:
            t = datetime.fromtimestamp(ts_ms / 1000.0)
            if t < earliest or t > now + timedelta(hours=1):
                continue
            day_idx = (t.date() - earliest.date()).days
            hour_idx = t.hour
            if 0 <= day_idx < 7 and 0 <= hour_idx < 24:
                grid[day_idx, hour_idx] += value
        if grid.max() > 0:
            norm = grid / grid.max()
        else:
            norm = grid
        # Transpose so day-0 (oldest) is at the top.
        img = pg.ImageItem(np.flipud(norm))
        cmap = None
        for name in ("viridis", "plasma", "inferno", "magma", "CET-D1", "greys"):
            try:
                cmap = pg.colormap.get(name)
                if cmap is not None:
                    break
            except Exception:
                continue
        if cmap is not None:
            img.setColorMap(cmap)
        self.plot.addItem(img)
        self._img = img
        ax = self.plot.getAxis("left")
        ax.setTicks([
            list(zip(
                [0, 1, 2, 3, 4, 5, 6],
                ["", "Wed", "", "Fri", "", "Sun", ""],
            ))
        ])
        bx = self.plot.getAxis("bottom")
        bx.setTicks([list(zip(range(24), ["" if h % 6 else str(h) for h in range(24)]))])
        self.plot.setXRange(-0.5, 23.5)
        self.plot.setYRange(-0.5, 6.5)
        img.setRect(0, 0, 24, 7)
