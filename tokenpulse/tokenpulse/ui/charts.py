"""Reusable chart widgets built on pyqtgraph."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Optional

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QVBoxLayout, QWidget


def _pick_cn_font() -> str:
    """Pick a font family that renders Chinese characters on this platform."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase
    app = QApplication.instance()
    if app is None:
        return "Microsoft YaHei"
    fams = set(QFontDatabase.families())
    for cand in ("Microsoft YaHei", "Microsoft YaHei UI", "Noto Sans SC",
                 "PingFang SC", "Source Han Sans SC", "SimHei", "SimSun"):
        if cand in fams:
            return cand
    return "Microsoft YaHei"


_CN_FONT = _pick_cn_font()
# pyqtgraph uses Qt's rendering pipeline.  We force a dark, high-DPI
# style that matches the rest of the app.
pg.setConfigOption("background", "#FFFFFF")
pg.setConfigOption("foreground", "#605E5C")
pg.setConfigOption("antialias", True)


class TimeSeriesChart(QWidget):
    """A live line chart of tokens-per-minute per tool."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.plot = pg.PlotWidget(title="")
        self.plot.showGrid(x=True, y=True, alpha=0.5)
        self.plot.setBackground("#FFFFFF")
        self.plot.setLabel("left", "Token数", **{"font-family": _CN_FONT, "font-size": "11px"})

        self.plot.setLabel("bottom", "时间", **{"font-family": _CN_FONT, "font-size": "11px"})

        self.plot.getPlotItem().setMenuEnabled(False)
        self.plot.setMouseEnabled(x=True, y=False)
        # Force Chinese-capable font on tick labels.
        tick_font = QFont(_CN_FONT, 9)
        for axis_name in ("left", "bottom", "right", "top"):
            try:
                self.plot.getAxis(axis_name).label.setFont(tick_font)
                self.plot.getAxis(axis_name).setStyle(tickFont=tick_font)
            except Exception:
                pass
        layout.addWidget(self.plot)

        self._curves: dict[str, pg.PlotDataItem] = {}
        self._buckets: dict[str, Deque[tuple[float, float]]] = defaultdict(
            lambda: deque(maxlen=240)  # 4 hours at 1-minute buckets
        )
        self._colors = {
            "codex": "#0078D4",
            "claude-code": "#8661C5",
            "total": "#107C10",
        }
        legend = self.plot.addLegend(offset=(10, 10))
        legend.setBrush("#FFFFFF")
        legend.setPen("#EDEBE9")
        # Style legend text dark for light theme
        try:
            for label_item in legend.items:
                if len(label_item) >= 2:
                    label_item[1].setAttr("color", "#1F1F1F")
        except Exception:
            pass

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
            color = self._colors.get(tool, "#0078D4")
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
        "input": "#0078D4",
        "output": "#107C10",
        "cache_read": "#8661C5",
        "cache_write": "#FF8C00",
        "thinking": "#D13438",
    }
    LABELS = {
        "input": "输入",
        "output": "输出",
        "cache_read": "缓存读取",
        "cache_write": "缓存写入",
        "thinking": "思考",
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.PlotWidget()
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()
        self.plot.getPlotItem().setMenuEnabled(False)
        self.plot.setBackground("#FFFFFF")
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
                text=f"{total:,}", color="#1F1F1F", anchor=(0, 0.5)
            )
            label.setPos(left[idx], idx)
            self.plot.addItem(label)

# ---------------------------------------------------------------- palette
_PALETTE = [
    "#0078D4",  # Microsoft blue
    "#107C10",  # green
    "#FF8C00",  # orange
    "#8661C5",  # purple
    "#D13438",  # red
    "#00B294",  # teal
    "#B146C2",  # magenta
    "#008272",  # dark teal
    "#A4262C",  # dark red
    "#CA5010",  # dark orange
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
    """Donut/pie chart of total tokens by model + side legend.

    重构版: 把易重叠的扇区标签换成右侧图例, 即使 6+ 个模型
    也能在一屏内清晰展示.  布局: [ Donut | Legend list ].
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        from PySide6.QtWidgets import (
            QHBoxLayout, QVBoxLayout, QScrollArea, QFrame, QLabel,
            QSizePolicy,
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 左侧: 饼图绘制区
        self.view = pg.GraphicsView()
        self.view.setBackground("#FFFFFF")
        self.view.setRenderHint(QPainter.Antialiasing, True)
        self.view.setMinimumWidth(110)
        layout.addWidget(self.view, stretch=3)

        # 右侧: 滚动图例
        self._legend_scroll = QScrollArea()
        self._legend_scroll.setWidgetResizable(True)
        self._legend_scroll.setFrameShape(QFrame.NoFrame)
        self._legend_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._legend_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._legend_scroll.setStyleSheet("background: transparent;")
        layout.addWidget(self._legend_scroll, stretch=4)

        self._legend_host = QWidget()
        self._legend_host.setStyleSheet("background: transparent;")
        self._legend_layout = QVBoxLayout(self._legend_host)
        self._legend_layout.setContentsMargins(2, 0, 2, 0)
        self._legend_layout.setSpacing(2)
        self._legend_layout.addStretch(1)
        self._legend_scroll.setWidget(self._legend_host)

        self._items: list = []
        self._labels: list[pg.TextItem] = []
        self._data: dict = {}
        self._pending = False
        self.view.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self.view and event.type() in (QEvent.Resize, QEvent.Show):
            self._schedule_render()
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_render()

    def _schedule_render(self):
        if self._pending or not self._data:
            return
        self._pending = True
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._do_render)

    def _do_render(self):
        self._pending = False
        self._render(self._data)

    def set_data(self, model_totals: dict) -> None:
        self._data = dict(model_totals)
        self._schedule_render()

    def _clear_legend(self) -> None:
        # remove all rows except the trailing stretch
        while self._legend_layout.count() > 1:
            item = self._legend_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _add_legend_row(self, color: str, name: str, pct: float) -> None:
        from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget, QSizePolicy
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 1, 0, 1)
        h.setSpacing(6)
        swatch = QLabel()
        swatch.setFixedSize(10, 10)
        swatch.setStyleSheet(
            f"background:{color}; border-radius:2px;"
        )
        h.addWidget(swatch, 0)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            "color:#1F1F1F; font-size:11px; background:transparent;"
        )
        name_lbl.setToolTip(name)
        name_lbl.setMaximumWidth(110)
        name_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        h.addWidget(name_lbl, 1)
        pct_lbl = QLabel(f"{pct:.0f}%")
        pct_lbl.setStyleSheet(
            "color:#605E5C; font-size:11px; font-weight:600; background:transparent;"
        )
        pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(pct_lbl, 0)
        self._legend_layout.insertWidget(
            self._legend_layout.count() - 1, row
        )

    def _render(self, model_totals: dict) -> None:
        # 清理旧的图形元素
        for it in self._items:
            self.view.removeItem(it)
        for lbl in self._labels:
            self.view.removeItem(lbl)
        self._items.clear()
        self._labels.clear()
        self._clear_legend()

        # 把小扇区合并为「其他」, 避免图例过长
        items = sorted(model_totals.items(), key=lambda kv: -kv[1])
        if not items:
            return
        total = sum(v for _, v in items)
        if total == 0:
            return
        threshold = total * 0.05
        main = [(k, v) for k, v in items if v >= threshold]
        other = sum(v for k, v in items if v < threshold)
        if other > 0:
            main.append(("其他", other))

        import math
        # 用 view 自己的 viewport 尺寸, 1:1 映射
        viewport_size = self.view.viewport().size()
        w = max(viewport_size.width(), 110)
        h = max(viewport_size.height(), 150)
        radius = min(w, h) * 0.40
        if radius < 32.0:
            radius = 32.0
        cx, cy = w / 2, h / 2
        inner = radius * 0.55

        slice_font = QFont(_CN_FONT, 9)
        slice_font.setBold(False)

        # 1. 画扇区
        start_angle = -math.pi / 2
        for label, value in main:
            sweep = 2 * math.pi * (value / total)
            color = _color_for(label)
            path_item = _make_donut_slice(
                cx, cy, radius, inner,
                start_angle, start_angle + sweep, color
            )
            self.view.addItem(path_item)
            self._items.append(path_item)
            start_angle += sweep

        # 2. 中心: 总数 + 副标题
        total_text = pg.TextItem(
            text=_humanize(total), color="#1F1F1F", anchor=(0.5, 0.5),
        )
        f = QFont(_CN_FONT, 12)
        f.setBold(True)
        total_text.setFont(f)
        total_text.setPos(cx, cy - 4)
        self.view.addItem(total_text)
        self._labels.append(total_text)

        sub_text = pg.TextItem(
            text="总 Token", color="#8A8A8E", anchor=(0.5, 0.5),
        )
        sf = QFont(_CN_FONT, 8)
        sub_text.setFont(sf)
        sub_text.setPos(cx, cy + 12)
        self.view.addItem(sub_text)
        self._labels.append(sub_text)

        # 3. 右侧图例
        for label, value in main:
            pct = value / total * 100
            self._add_legend_row(_color_for(label), label, pct)

        # 4. SceneRect 1:1 同步
        self.view.setSceneRect(0, 0, w, h)
        self.view.resetTransform()

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
    item.setPen(QPen(QColor("#FFFFFF"), 1))
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
        self.plot.setBackground("#FFFFFF")
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
