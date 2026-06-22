# -*- coding: utf-8 -*-
"""TokenPulse \u7d27\u51d1\u6982\u89c8\u7a97\u53e3\u3002

\u53c2\u8003\u8bbe\u8ba1\uff1a\u4e09\u4e2a KPI \u5361\u7247\u9876\u90e8 + \u6a2a\u5411\u6761\u5f62\u56fe\uff08\u6309\u6a21\u578b\uff09\u3002
\u8f7b\u91cf\u3001\u6696\u8272\u8c03\u3001\u4ec5\u4f7f\u7528 QPainter \u4e0d\u4f9d\u8d56 pyqtgraph\u3002

\u4e94\u4e2a\u72ec\u7acb\u7c7b\uff0c\u5747\u4e3a\u53ef\u63d2\u62d4\u3001\u53ef\u590d\u7528\u5355\u5143\uff1a
  WarmCard        \u5e26\u8f6f\u9634\u5f71\u7684\u767d\u8272\u5361\u7247
  KPIWidget       \u7d27\u51d1 KPI \u5361\u7247\uff0812px \u5706\u89d2\uff09
  QuotaBar        \u5c0f\u578b\u8fdb\u5ea6\u6761
  WarmHorizontalBar  \u6309\u6a21\u578b\u7684\u6a2a\u5411\u6761\u5f62\u56fe
  OverviewWindow  \u4e3b\u7a97\u53e3\uff0c\u4e09 KPI + \u6761\u5f62\u56fe
"""

from __future__ import annotations

import datetime
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


# \u53c2\u8003\u8bbe\u8ba1\u7684\u6696\u8272\u8c03
PALETTE = {
    "bg":         "#F7F7F8",
    "card":       "#FFFFFF",
    "text":       "#333333",
    "text_sub":   "#8A8A8E",
    "saving":     "#4CAF50",
    "accent":     "#F29C38",   # \u4e3b\u8d34\u8272
    "accent_alt": "#81B29A",   # \u9c7c\u5c3e\u8349\u7eff
    "warn":       "#E2A03F",
    "danger":     "#D9534F",
    "grid":       "#EAEAEA",
}


# ---------------------------------------------------------------- WarmCard
class WarmCard(QFrame):
    """\u5e26\u8f6f\u9634\u5f71\u7684\u767d\u8272\u5361\u7247\u3002\u9ed8\u8ba4 12px \u5706\u89d2\u3002"""

    def __init__(self, parent: Optional[QWidget] = None, radius: int = 12) -> None:
        super().__init__(parent)
        self.setObjectName("warmCard")
        self.setStyleSheet(
            f"""
            QFrame#warmCard {{
                background-color: {PALETTE["card"]};
                border-radius: {radius}px;
                border: none;
            }}
            """
        )
        # \u4ec5\u4e3a\u9876\u90e8\u4e3b\u5361\u7247\u52a0\u9634\u5f71\uff0cKPIWidget \u5185\u90e8\u4e0d\u91cd\u590d\u52a0\u3002
        if parent is None or not isinstance(parent, WarmCard):
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(20)
            shadow.setColor(QColor(0, 0, 0, 8))
            shadow.setOffset(0, 4)
            self.setGraphicsEffect(shadow)


# ---------------------------------------------------------------- KPIWidget
class KPIWidget(QFrame):
    """\u7d27\u51d1 KPI \u5361\u7247\uff1a\u6807\u9898 + \u5927\u6570\u5b57 + \u53ef\u9009\u526f\u6587\u672c\u3002"""

    def __init__(
        self,
        title: str,
        value: str,
        sub_text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("kpiCard")
        self.setStyleSheet(
            f"""
            QFrame#kpiCard {{
                background-color: {PALETTE["card"]};
                border-radius: 12px;
                border: none;
            }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        self._title = QLabel(title)
        self._title.setStyleSheet(
            f"color: {PALETTE['text_sub']}; font-size: 11px; background: transparent;"
        )

        self._value = QLabel(value)
        f = QFont()
        f.setPointSize(20)
        f.setBold(True)
        self._value.setFont(f)
        self._value.setStyleSheet(
            f"color: {PALETTE['text']}; background: transparent;"
        )

        layout.addWidget(self._title)
        layout.addWidget(self._value)

        self._sub = None
        if sub_text:
            self._sub = QLabel(sub_text)
            self._sub.setStyleSheet(
                f"color: {PALETTE['saving']}; font-size: 10px; background: transparent;"
            )
            layout.addWidget(self._sub)

    # \u8ba9\u5916\u90e8\u53ef\u4ee5\u968f\u65f6\u66f4\u65b0\u5185\u5bb9
    def setValue(self, value: str) -> None:
        self._value.setText(value)

    def setSub(self, text: str, color: str = None) -> None:
        if color is None:
            color = PALETTE["saving"]
        if self._sub is None:
            # 为什么创建时没 sub text？此处补创建
            self._sub = QLabel(text or "")
            self._sub.setStyleSheet(
                f"color: {color}; font-size: 10px; background: transparent;"
            )
            self.layout().addWidget(self._sub)
        if not text:
            self._sub.setVisible(False)
            return
        self._sub.setVisible(True)
        self._sub.setText(text)
        self._sub.setStyleSheet(
            f"color: {color}; font-size: 10px; background: transparent;"
        )


# ---------------------------------------------------------------- QuotaBar
class QuotaBar(QWidget):
    """\u7d27\u51d1\u8fdb\u5ea6\u6761\u3002\u8d85\u8fc7 70% \u53d8\u9ec4\u3001\u8d85\u8fc7 90% \u53d8\u8d64\u3002"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._value: float = -1.0
        self.setMinimumHeight(6)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def setValue(self, ratio: float) -> None:
        self._value = max(-1.0, min(1.0, float(ratio)))
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 0, self.width(), self.height())
        radius = rect.height() / 2
        painter.setBrush(QBrush(QColor(PALETTE["grid"])))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, radius, radius)
        if self._value < 0:
            return
        if self._value >= 0.90:
            color = QColor(PALETTE["danger"])
        elif self._value >= 0.70:
            color = QColor(PALETTE["warn"])
        else:
            color = QColor(PALETTE["accent_alt"])
        fill = QRectF(rect)
        fill.setWidth(rect.width() * self._value)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(fill, radius, radius)


# ---------------------------------------------------------------- WarmHorizontalBar
class WarmHorizontalBar(QWidget):
    """\u6a2a\u5411\u6761\u5f62\u56fe\uff0c\u7528\u4e8e\u6309\u6a21\u578b\u6d88\u8017\u5206\u5e03\u3002

    \u8c03\u7528\u65b9\u5f0f\uff1a
        chart = WarmHorizontalBar()
        chart.setData([("Claude 3.5", 75000), ("DeepSeek", 35000), ("GPT-4o", 15000)])

    \u53ef\u9009\u53c2\u6570\uff1a
        top_n  \u53ea\u663e\u793a\u524d N \u4e2a\u3002\u9ed8\u8ba4 8\u3002
        \u9ed8\u8ba4\u4ee5\u4e0a\u8fdb\u884c\u53ef\u89c6\u5316\u3002
    """

    BAR_HEIGHT = 16          # \u6bcf\u6761\u7684\u9ad8\u5ea6
    BAR_SPACING = 8          # \u6761\u4e4b\u95f4\u7684\u5782\u76f4\u95f4\u8ddd
    LABEL_WIDTH = 110         # \u5de6\u4fa7\u6a21\u578b\u540d\u7684\u4e08\u91cf
    VALUE_WIDTH = 60         # \u53f3\u4fa7\u6570\u503c\u7684\u4e08\u91cf
    LEFT_PAD = 12            # \u5361\u7247\u5de6\u5185\u8fb9\u8ddd
    RIGHT_PAD = 12

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._items: List[Tuple[str, float, QColor]] = []
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # \u4f7f\u80cc\u666f\u900f\u660e\uff0c\u8d4c\u5728\u4e0a\u5c42 WarmCard \u4e0a\u9762
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def setData(self, items: Sequence[Tuple[str, float]]) -> None:
        """\u63a5\u6536 (label, value) \u5217\u8868\uff0c\u81ea\u52a8\u6309\u503c\u4ece\u5927\u5230\u5c0f\u6392\u5e8f\u3002"""
        if not items:
            self._items = []
            self.update()
            return
        # \u6309\u503c\u964d\u5e8f\u6392\u5e8f
        sorted_items = sorted(items, key=lambda x: -x[1])
        # \u4e3a\u6bcf\u4e2a\u6761\u9009\u4e00\u4e2a\u989c\u8272\uff08\u53ef\u9009\u8c03\u8272\u677f\uff09
        base_hues = [
            QColor(PALETTE["accent"]),
            QColor(PALETTE["accent_alt"]),
            QColor("#E2A03F"),
            QColor("#6F9BD1"),
            QColor("#C76B98"),
            QColor("#9D7AD0"),
            QColor("#5BAA8E"),
            QColor("#D88C5B"),
        ]
        self._items = []
        for i, (label, val) in enumerate(sorted_items):
            color = base_hues[i % len(base_hues)]
            self._items.append((str(label), float(val), color))
        self.update()

    def sizeHint(self):
        # \u9ad8\u5ea6 \u968f\u6761\u6570\u52a8\u6001\u53d8\u5316
        h = len(self._items) * (self.BAR_HEIGHT + self.BAR_SPACING) + 8
        return self.minimumSize().expandedTo(self.size())

    def paintEvent(self, _event) -> None:
        if not self._items:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w = float(self.width())
        h = float(self.height())
        max_v = max(v for _, v, _ in self._items) or 1.0

        label_x = self.LEFT_PAD
        bar_x0 = self.LEFT_PAD + self.LABEL_WIDTH
        value_x = w - self.RIGHT_PAD - self.VALUE_WIDTH
        bar_max_w = max(20.0, value_x - bar_x0 - 6)

        y = 4.0
        for label, val, color in self._items:
            # 1) \u6a21\u578b\u540d
            painter.setPen(QColor(PALETTE["text"]))
            f = QFont()
            f.setPointSize(9)
            painter.setFont(f)
            label_rect = QRectF(label_x, y, self.LABEL_WIDTH - 6, self.BAR_HEIGHT)
            painter.drawText(
                label_rect, Qt.AlignLeft | Qt.AlignVCenter, label
            )
            # 2) \u6761\u5f62
            ratio = max(0.0, min(1.0, val / max_v))
            bar_w = bar_max_w * ratio
            bar_rect = QRectF(bar_x0, y, bar_w, self.BAR_HEIGHT)
            # \u5de6\u4fa7\u7528\u9c7c\u5c3e\u8349\u7eff\uff0c\u53f3\u4fa7\u4e3a\u9ec4\u8272\u6e10\u53d8\uff0c\u8d8a\u957f\u8d8a\u6696\u8d8a\u70ed
            grad = QLinearGradient(bar_x0, 0, bar_x0 + bar_max_w, 0)
            grad.setColorAt(0.0, QColor(PALETTE["accent_alt"]))
            grad.setColorAt(1.0, color)
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bar_rect, self.BAR_HEIGHT / 2, self.BAR_HEIGHT / 2)
            # 3) \u53f3\u4fa7\u503c\uff08\u4eba\u6027\u5316\u663e\u793a\uff09
            painter.setPen(QColor(PALETTE["text_sub"]))
            value_rect = QRectF(value_x, y, self.VALUE_WIDTH, self.BAR_HEIGHT)
            text = self._humanize(val)
            painter.drawText(value_rect, Qt.AlignRight | Qt.AlignVCenter, text)

            y += self.BAR_HEIGHT + self.BAR_SPACING

    @staticmethod
    def _humanize(n: float) -> str:
        a = abs(int(n))
        if a >= 1_000_000_000:
            return f"{n/1_000_000_000:.2f}B"
        if a >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if a >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(int(n))


# ---------------------------------------------------------------- \u6570\u636e\u51c6\u5907
@dataclass
class OverviewSnapshot:
    today_tokens: int                # \u4eca\u65e5\u8f93\u5165+\u8f93\u51fa token \u603b\u548c
    today_cost: float
    saved_cost: float
    primary_pct: Optional[float]     # 5h \u52a8\u6001\u914d\u989d
    weekly_change_pct: float         # \u4eca\u65e5 vs \u4e0a\u5468\u540c\u671f\u7684\u53d8\u5316 %
    weekly_state: str                # "\u4e0a\u6da8" / "\u4e0b\u964d" / "\u5e73\u7a33"
    model_breakdown: List[Tuple[str, int]]  # \u6309\u6a21\u578b\u5212\u5206\u7684\u8fd1\u4e00\u5468 token \u603b\u91cf


# ---------------------------------------------------------------- \u4e3b\u63a7\u4ef6
class OverviewWindow(QWidget):
    """\u7d27\u51d1\u6982\u89c8\u7a97\u53e3\u3002

    \u5e03\u5c40\uff1a
        \u9876\u90e8\uff1a3 \u4e2a KPI \u5361\uff08\u4eca\u65e5\u603b\u91cf / 5h \u914d\u989d / 7 \u65e5\u8d8b\u52bf\uff09
        \u4e2d\u90e8\uff1a\u6807\u9898 + \u6a2a\u5411\u6761\u5f62\u56fe\uff08\u6309\u6a21\u578b\uff09
    """

    closed = Signal()

    def __init__(self, storage, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._storage = storage
        self.setWindowTitle("TokenPulse \u00b7 \u6982\u89c8")
        self.resize(640, 460)
        self.setStyleSheet(f"background-color: {PALETTE['bg']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # ---------- 1. \u9876\u90e8\u4e09 KPI \u884c ---------------------------------------
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        self._kpi_today = KPIWidget("\u4eca\u65e5\u603b\u91cf", "\u2014", "\u8282\u7701 \u2014")
        self._kpi_quota = KPIWidget("5\u5c0f\u65f6\u914d\u989d", "\u2014", "")
        self._kpi_trend = KPIWidget("7\u65e5\u8d8b\u52bf", "\u2014", "")
        kpi_row.addWidget(self._kpi_today, 1)
        kpi_row.addWidget(self._kpi_quota, 1)
        kpi_row.addWidget(self._kpi_trend, 1)
        root.addLayout(kpi_row)

        # 5h \u914d\u989d\u5361\u5185\u5d4c\u5165\u8fdb\u5ea6\u6761\uff08\u53c2\u8003\u539f\u53c2\u8003\u4ee3\u7801\u63d0\u793a\uff09
        quota_layout = self._kpi_quota.layout()
        if quota_layout is not None:
            self._quota_bar = QuotaBar()
            # \u5d4c\u5165\u5230 sub \u6587\u672c\u4e0b\u9762
            quota_layout.addWidget(self._quota_bar)
        else:
            self._quota_bar = QuotaBar(self)

        # ---------- 2. \u4e2d\u90e8\u6807\u9898 + \u6a2a\u5411\u6761\u5f62\u56fe ------------------------
        self._model_card = WarmCard()
        model_layout = QVBoxLayout(self._model_card)
        model_layout.setContentsMargins(14, 12, 14, 12)
        model_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self._model_title = QLabel("\u5404\u6a21\u578b\u6d88\u8017\u5206\u5e03")
        self._model_title.setStyleSheet(
            f"color: {PALETTE['text_sub']}; font-size: 12px; font-weight: bold; background: transparent;"
        )
        self._model_sub = QLabel("")
        self._model_sub.setStyleSheet(
            f"color: {PALETTE['text_sub']}; font-size: 11px; background: transparent;"
        )
        self._model_sub.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        title_row.addWidget(self._model_title)
        title_row.addWidget(self._model_sub, 1)
        model_layout.addLayout(title_row)

        self._hbar = WarmHorizontalBar()
        model_layout.addWidget(self._hbar, 1)

        root.addWidget(self._model_card, 1)

        # ---------- \u5b9a\u671f\u5237\u65b0 -------------------------------------------------
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(10_000)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start()
        self.refresh()

    # ---------------------------------------------------------- \u6570\u636e\u91c7\u96c6
    def refresh(self) -> None:
        snap = self._collect_snapshot()
        self._render_today(snap)
        self._render_quota(snap)
        self._render_trend(snap)
        self._render_models(snap)

    def _collect_snapshot(self) -> OverviewSnapshot:
        s = self._storage
        now = int(time.time() * 1000)
        today_start = int(
            datetime.datetime.combine(
                datetime.date.today(), datetime.time.min
            ).timestamp() * 1000
        )

        # \u4eca\u65e5\u603b\u91cf
        today_in = today_out = today_cost = cache_read = 0
        today_tot = None
        for hour_ts, t in s.hourly(0):
            if hour_ts * 3600_000 >= today_start:
                if today_tot is None:
                    today_tot = t
                else:
                    today_tot.add(t)
        if today_tot is not None:
            today_in = today_tot.input_tokens
            today_out = today_tot.output_tokens
            today_cost = today_tot.cost
            cache_read = today_tot.cache_read_tokens
        today_total = today_in + today_out
        saved = round(today_cost * (cache_read / max(today_in + cache_read, 1)) * 0.5, 2)

        # 5h \u914d\u989d
        rate = s.latest_rate_limit()
        primary_pct = rate.primary_used_percent if rate and rate.primary_used_percent is not None else None

        # 7 \u65e5\u8d8b\u52bf\uff1a\u4eca\u5929 vs \u4e0a\u4e00\u5468\u540c\u671f
        weekly_change, state = self._compute_weekly_change(s, today_start, now)
        # \u8fd1\u4e00\u5468 token \u603b\u91cf\uff08\u4e0d\u662f\u4eca\u5929\uff09
        week_start = today_start - 6 * 24 * 3600_0000
        model_breakdown = self._models_in_window(s, week_start, now)

        return OverviewSnapshot(
            today_tokens=today_total,
            today_cost=today_cost,
            saved_cost=saved,
            primary_pct=primary_pct,
            weekly_change_pct=weekly_change,
            weekly_state=state,
            model_breakdown=model_breakdown,
        )

    def _compute_weekly_change(self, s, today_start: int, now: int) -> Tuple[float, str]:
        """\u4eca\u5929 vs \u4e0a\u4e00\u5468\u540c\u671f\u7684 token \u53d8\u5316\u3002\u4e0a\u4e00\u5468\u540c\u671f\u4e3a (today_start-7d, today_start)\u3002"""
        last_week_start = today_start - 7 * 24 * 3600_0000
        last_week_total = self._sum_tokens(s, last_week_start, today_start)
        today_total = self._sum_tokens(s, today_start, now)
        if last_week_total <= 0:
            if today_total > 0:
                return 100.0, "\u4e0a\u6da8"
            return 0.0, "\u5e73\u7a33"
        delta_pct = (today_total - last_week_total) / last_week_total * 100.0
        if abs(delta_pct) < 5.0:
            state = "\u5e73\u7a33"
        elif delta_pct > 0:
            state = "\u4e0a\u6da8"
        else:
            state = "\u4e0b\u964d"
        return delta_pct, state

    def _sum_tokens(self, s, start_ms: int, end_ms: int) -> int:
        total = 0
        for hour_ts, t in s.hourly(0):
            hour_ms = hour_ts * 3600_000
            if hour_ms < start_ms:
                continue
            if hour_ms >= end_ms:
                break
            total += t.input_tokens + t.output_tokens
        return total

    def _models_in_window(
        self, s, start_ms: int, end_ms: int
    ) -> List[Tuple[str, int]]:
        """\u8fd1 7 \u5929\u6309\u6a21\u578b\u8ba1\u7b97\u8f93\u5165+\u8f93\u51fa\u603b\u548c\u3002"""
        rows: dict[str, int] = {}
        with s._lock:
            cur = s._conn.execute(
                """
                SELECT model,
                       SUM(input_tokens) AS inp,
                       SUM(output_tokens) AS out
                FROM usage_records
                WHERE ts >= ? AND ts < ?
                GROUP BY model
                ORDER BY (inp + out) DESC
                LIMIT 8
                """,
                (start_ms, end_ms),
            )
            for r in cur.fetchall():
                model = r[0] or "unknown"
                rows[model] = int(r[1] or 0) + int(r[2] or 0)
        return list(rows.items())

    # ---------------------------------------------------------- \u6e32\u67d3
    def _humanize_int(self, n: int) -> str:
        a = abs(int(n))
        if a >= 1_000_000_000:
            return f"{n/1_000_000_000:.2f}B"
        if a >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if a >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(int(n))

    def _render_today(self, snap: OverviewSnapshot) -> None:
        self._kpi_today.setValue(self._humanize_int(snap.today_tokens))
        if snap.saved_cost > 0:
            self._kpi_today.setSub(f"\u8282\u7701 ${snap.saved_cost:.2f}")
        else:
            self._kpi_today.setSub("")

    def _render_quota(self, snap: OverviewSnapshot) -> None:
        if snap.primary_pct is None:
            self._kpi_quota.setValue("\u2014")
            self._quota_bar.setValue(-1)
            return
        pct = snap.primary_pct
        if pct >= 90:
            state = "\u9ad8\u538b"
        elif pct >= 70:
            state = "\u8b66\u544a"
        else:
            state = "\u5065\u5eb7"
        self._kpi_quota.setValue(f"{pct:.0f}%")
        self._kpi_quota.setSub(state)
        self._quota_bar.setValue(pct / 100.0)

    def _render_trend(self, snap: OverviewSnapshot) -> None:
        if snap.weekly_state == "\u4e0a\u6da8":
            arrow = "\u2191"
            color = PALETTE["warn"]
        elif snap.weekly_state == "\u4e0b\u964d":
            arrow = "\u2193"
            color = PALETTE["saving"]
        else:
            arrow = "\u2192"
            color = PALETTE["text_sub"]
        self._kpi_trend.setValue(snap.weekly_state)
        self._kpi_trend.setSub(f"{arrow} {snap.weekly_change_pct:+.1f}%", color=color)

    def _render_models(self, snap: OverviewSnapshot) -> None:
        if not snap.model_breakdown:
            self._model_sub.setText("\u6682\u65e0\u6570\u636e")
            return
        peak = max(v for _, v in snap.model_breakdown)
        self._model_sub.setText(
            f"\u6700\u9ad8 {self._humanize_int(peak)} \u00b7 \u5171 {len(snap.model_breakdown)} \u4e2a\u6a21\u578b"
        )
        self._hbar.setData(snap.model_breakdown)

    # ---------------------------------------------------------- \u7a97\u53e3\u5173\u95ed
    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)
