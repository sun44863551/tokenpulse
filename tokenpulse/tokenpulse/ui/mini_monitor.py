"""A compact, always-on-top floating monitor widget for TokenPulse.

Design language: Vercel/Geist (the design system that powers v0).

Token sources (from @geist-ui/themes `src/default/index.styl`):
  --geist-background  #ffffff
  --accents-1         #fafafa
  --accents-2         #eaeaea
  --accents-3         #999999
  --accents-5         #666666
  --accents-7         #333333
  --accents-8         #111111
  --geist-success     #0070f3
  --geist-error       #ee0000
  --geist-warning     #f5a623
  --shadow-small      0 5px 10px rgba(0, 0, 0, 0.12)
  --shadow-medium     0 8px 30px rgba(0, 0, 0, 0.12)
  --geist-radius      5px

Floating panel rules used here (slightly larger than default 5px):
  * 10px rounded corners (8-12px range common for v0-style cards)
  * 1px subtle border using --accents-2 (#eaeaea)
  * 12px gap to top-right of the screen
  * Soft drop shadow that deepens on hover
  * 220ms entrance fade + 6px slide
  * Drag to reposition, click to expand the main window
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QPoint,
    QPropertyAnimation,
    QEasingCurve,
    QSize,
    Qt,
    QTimer,
    QEvent,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..app import AppController


# ---------------------------------------------------------------- palette
# Mirrors Vercel/Geist (v0) design tokens. Keep these in sync with
# styles.py so the widget blends into the main dashboard.
_G_BG          = "#ffffff"   # --geist-background
_G_BG_PAGE     = "#fafafa"   # --accents-1
_G_BORDER      = "#eaeaea"   # --accents-2 (subtle border)
_G_BORDER_HOV  = "#d4d4d4"   # --accents-2 darker
_G_MUTED       = "#999999"   # --accents-3
_G_TEXT_2      = "#666666"   # --accents-5
_G_TEXT_1      = "#333333"   # --accents-7
_G_HEADING     = "#111111"   # --accents-8
_G_ACCENT      = "#0070f3"   # --geist-success (Vercel blue)
_G_ERROR       = "#ee0000"   # --geist-error
_G_WARNING     = "#f5a623"   # --geist-warning

# Drop shadow (Geist --shadow-small)
_G_SHADOW_RGBA = "rgba(0, 0, 0, 60)"   # ~24% black, 0 5px 10px blur


# ---------------------------------------------------------------- helpers
def _humanize(n) -> str:
    """Compress large numbers to K/M/B/T for compact display."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    for unit, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if abs(n) >= unit:
            return f"{n / unit:,.1f}{suffix}".replace(".0", "")
    return f"{n:,.0f}"


def _format_money(amount: float) -> str:
    if amount >= 1:
        return "\u00a5%.2f" % amount
    if amount >= 0.01:
        return "\u00a5%.3f" % amount
    return "\u00a5%.4f" % amount


# ---------------------------------------------------------------- widget
class MiniMonitorWidget(QWidget):
    """Frameless, always-on-top, top-right anchored monitor card.

    Signals
    -------
    expand_requested()
        Emitted when the user clicks the body of the widget (or releases
        a click that did not move the widget). The host should connect
        this to its show / restore handler.
    quit_requested()
        Emitted when the user clicks the close button on the widget.
    """

    expand_requested = Signal()
    quit_requested = Signal()

    _MARGIN         = 16    # px from the top-right corner of the screen
    _DRAG_THRESHOLD = 4     # px movement that still counts as a click
    _FIXED_W        = 268
    _FIXED_H        = 96

    def __init__(self, controller: AppController, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._controller = controller

        # --- window flags: frameless, always-on-top tool window.
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(QSize(self._FIXED_W, self._FIXED_H))

        # --- state for dragging
        self._press_pos: Optional[QPoint] = None
        self._drag_offset: Optional[QPoint] = None
        self._last_total_tokens: Optional[float] = None
        self._last_cost: Optional[float] = None
        self._hovering: bool = False

        # --- build the card
        self._build()
        self._apply_shadow(_G_SHADOW_RGBA, blur=18, y_offset=4)

        # --- refresh loop
        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

        # --- entrance animation
        self.setWindowOpacity(0.0)
        self._animate_window_opacity(0.0, 1.0, 220, QEasingCurve.OutCubic)

        # populate immediately so the panel isn't blank on first show
        self._refresh()

    # --------------------------------------------------------------- build
    def _build(self) -> None:
        # Outer widget is transparent; the card sits inside with the shadow.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)  # room for the shadow
        outer.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("v0MiniMonitor")
        # Use v0 Geist tokens: white card + 1px subtle border + 10px radius
        self.card.setStyleSheet(
            """
            QFrame#v0MiniMonitor {
                background-color: %s;
                border: 1px solid %s;
                border-radius: 10px;
            }
            QFrame#v0MiniMonitor:hover {
                border-color: %s;
            }
            """
            % (_G_BG, _G_BORDER, _G_BORDER_HOV)
        )
        self.card.setCursor(Qt.PointingHandCursor)
        outer.addWidget(self.card)

        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(12, 10, 6, 10)
        card_layout.setSpacing(8)

        # --- left column: title + value + sub
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        title_row.setContentsMargins(0, 0, 0, 0)
        self.status_dot = QLabel("\u2022")  # bullet
        self.status_dot.setStyleSheet(
            "color: %s; font-size: 12px; font-weight: 800;"
            " background: transparent;" % _G_ACCENT
        )
        self.status_dot.setToolTip("Live: storage pipeline running")
        self.title_label = QLabel("TokenPulse")
        self.title_label.setStyleSheet(
            "color: %s; font-size: 11px; font-weight: 600;"
            " letter-spacing: 0.2px; background: transparent;"
            % _G_TEXT_2
        )
        title_row.addWidget(self.status_dot)
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        left.addLayout(title_row)

        # value row: big number + optional trend pill
        value_row = QHBoxLayout()
        value_row.setSpacing(6)
        value_row.setContentsMargins(0, 0, 0, 0)
        self.value_label = QLabel("\u2014")
        self.value_label.setStyleSheet(
            "color: %s; font-size: 22px; font-weight: 700;"
            " letter-spacing: -0.4px; background: transparent;"
            % _G_HEADING
        )
        self.trend_label = QLabel("")
        self.trend_label.setStyleSheet(
            "color: %s; font-size: 11px; font-weight: 600;"
            " background: transparent;" % _G_MUTED
        )
        self.trend_label.setVisible(False)
        value_row.addWidget(self.value_label, 0, Qt.AlignBottom)
        value_row.addWidget(self.trend_label, 0, Qt.AlignBottom)
        value_row.addStretch(1)
        left.addLayout(value_row)

        # sub row: cost / turns
        sub_row = QHBoxLayout()
        sub_row.setSpacing(10)
        sub_row.setContentsMargins(0, 0, 0, 0)
        self.cost_label = QLabel("费用 \u2014")
        self.cost_label.setStyleSheet(
            "color: %s; font-size: 11px; background: transparent;" % _G_MUTED
        )
        self.turns_label = QLabel("轮次 \u2014")
        self.turns_label.setStyleSheet(
            "color: %s; font-size: 11px; background: transparent;" % _G_MUTED
        )
        self.turns_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sub_row.addWidget(self.cost_label)
        sub_row.addStretch(1)
        sub_row.addWidget(self.turns_label)
        left.addLayout(sub_row)

        # right column: close button (small, top-right of card)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addStretch(1)
        self.close_btn = QLabel("\u00d7")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setAlignment(Qt.AlignCenter)
        self.close_btn.setStyleSheet(
            "color: %s; font-size: 16px; font-weight: 500;"
            " background: transparent; border-radius: 10px;"
            % _G_TEXT_2
        )
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setToolTip("退出 TokenPulse")
        self.close_btn.installEventFilter(self)
        right.addWidget(self.close_btn, 0, Qt.AlignRight | Qt.AlignTop)
        right.addStretch(1)

        card_layout.addLayout(left, 1)
        card_layout.addLayout(right, 0)

        # Install click-to-expand handler on the card body.
        self.card.installEventFilter(self)

    def _apply_shadow(self, color_rgba: str, blur: int = 18, y_offset: int = 4) -> None:
        eff = QGraphicsDropShadowEffect(self.card)
        eff.setBlurRadius(blur)
        eff.setOffset(0, y_offset)
        # Parse rgba string "rgba(r, g, b, a)" where a is 0-255
        try:
            inside = color_rgba[color_rgba.index("(") + 1 : color_rgba.index(")")]
            parts = [int(p.strip()) for p in inside.split(",")]
            r, g, b, a = parts[0], parts[1], parts[2], parts[3]
            eff.setColor(QColor(r, g, b, a))
        except Exception:
            eff.setColor(QColor(0, 0, 0, 60))
        self.card.setGraphicsEffect(eff)

    # -------------------------------------------------------- animation
    def _animate_window_opacity(self, frm: float, to: float, ms: int, easing) -> None:
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(ms)
        anim.setStartValue(frm)
        anim.setEndValue(to)
        anim.setEasingCurve(easing)
        anim.start()
        self._opacity_anim = anim  # keep alive

    def fade_out_and_hide(self) -> None:
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(180)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.finished.connect(self.hide)
        anim.start()
        self._opacity_anim = anim

    # ----------------------------------------------------------- data
    @Slot()
    def _refresh(self) -> None:
        try:
            storage = self._controller.storage()
            totals = storage.totals()
            rate = storage.latest_rate_limit()
        except Exception:
            return

        prev_tokens = self._last_total_tokens
        self._last_total_tokens = float(totals.total_tokens)
        self.value_label.setText(_humanize(totals.total_tokens))
        self._update_trend(prev_tokens, self._last_total_tokens)
        self.cost_label.setText("费用 " + _format_money(totals.cost))
        self.turns_label.setText("轮次 %d" % totals.interactions)
        self._update_status_dot(rate)

    def _update_trend(self, prev: Optional[float], current: float) -> None:
        if prev is None or prev <= 0 or current is None:
            self.trend_label.setVisible(False)
            return
        delta = current - prev
        pct = delta / prev * 100.0
        # Only show meaningful deltas: at least 0.5% and >100 tokens
        if abs(pct) < 0.5 or abs(delta) < 100:
            self.trend_label.setVisible(False)
            return
        if delta > 0:
            # tokens increasing: neutral, no color emphasis
            self.trend_label.setText("\u2191 %.1f%%" % abs(pct))
            self.trend_label.setStyleSheet(
                "color: %s; font-size: 11px; font-weight: 600;"
                " background: transparent;" % _G_MUTED
            )
        else:
            self.trend_label.setText("\u2193 %.1f%%" % abs(pct))
            self.trend_label.setStyleSheet(
                "color: %s; font-size: 11px; font-weight: 600;"
                " background: transparent;" % _G_ACCENT
            )
        self.trend_label.setVisible(True)

    def _update_status_dot(self, rate) -> None:
        """Pick a status dot colour and tooltip that match the
        Codex state.  Mirrors the dashboard's `_render_rate_card`
        so a MiniMax-M3 user never sees a misleading "low" dot.
        """
        # --- case A: no data at all (rate is None, or the snapshot
        # has no quota information because the active model is
        # provided by a third party such as MiniMax-M3).
        if rate is None or not getattr(rate, "has_quota_data", False):
            self.status_dot.setStyleSheet(
                "color: %s; font-size: 12px; font-weight: 800;"
                " background: transparent;" % _G_MUTED
            )
            if rate is None:
                self.status_dot.setToolTip("等待 Codex 发送频率数据")
            else:
                self.status_dot.setToolTip(
                    "当前模型不计入 Codex 5小时/周额度限制"
                )
            return

        # --- case B: hard rate-limit hit (Codex says we are out) ----
        reached = getattr(rate, "rate_limit_reached_type", None) or ""
        if reached in ("primary", "secondary", "both", "credit"):
            self.status_dot.setStyleSheet(
                "color: %s; font-size: 12px; font-weight: 800;"
                " background: transparent;" % _G_ERROR
            )
            self.status_dot.setToolTip(
                {
                    "primary": "5小时额度已用完",
                    "secondary": "周额度已用完",
                    "both": "5小时 + 周额度均已用完",
                    "credit": "Credits 已用完",
                }.get(reached, "频率限制已触发")
            )
            return

        # --- case C: normal percentage -------------------------------
        primary = rate.primary_used_percent or 0
        secondary = rate.secondary_used_percent or 0
        if primary >= 90 or secondary >= 90:
            color, tip = _G_ERROR, "用量接近上限"
        elif primary >= 70 or secondary >= 70:
            color, tip = _G_WARNING, "用量较高"
        else:
            color, tip = _G_ACCENT, "数据实时同步"
        self.status_dot.setStyleSheet(
            "color: %s; font-size: 12px; font-weight: 800;"
            " background: transparent;" % color
        )
        self.status_dot.setToolTip(tip)

    # ------------------------------------------------- positioning
    def move_to_top_right(self) -> None:
        screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        w, h = self.width(), self.height()
        x = avail.right() - w - self._MARGIN + 1
        y = avail.top() + self._MARGIN
        self.move(x, y)

    def sizeHint(self) -> QSize:
        return QSize(self._FIXED_W, self._FIXED_H)

    # ----------------------------------------------------- events
    def eventFilter(self, obj, event):
        # close button click
        if obj is self.close_btn and event.type() == QEvent.MouseButtonPress:
            if isinstance(event, QMouseEvent) and event.button() == Qt.LeftButton:
                self.quit_requested.emit()
                return True
        # card body click -> expand
        if obj is self.card and event.type() == QEvent.MouseButtonPress:
            if isinstance(event, QMouseEvent) and event.button() == Qt.LeftButton:
                if self.close_btn.geometry().contains(event.pos()):
                    return False
                self.expand_requested.emit()
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_offset
            screen = QGuiApplication.screenAt(new_pos) or QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                w, h = self.width(), self.height()
                new_pos.setX(max(avail.left(), min(new_pos.x(), avail.right() - w + 1)))
                new_pos.setY(max(avail.top(), min(new_pos.y(), avail.bottom() - h + 1)))
            self.move(new_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            if self._press_pos is not None:
                moved = (event.globalPosition().toPoint() - self._press_pos).manhattanLength()
                if moved <= self._DRAG_THRESHOLD:
                    self.expand_requested.emit()
        self._press_pos = None
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    # ------------------------------------------------ lifecycle
    def showEvent(self, event):
        super().showEvent(event)
        self.move_to_top_right()
        if not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()
