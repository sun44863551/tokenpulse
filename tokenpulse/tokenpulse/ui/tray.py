"""System tray icon + a compact popup window for at-a-glance stats (light theme)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPixmap,
    QPen,
    QBrush,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ..app import AppController
from ..storage.db import Totals


# ---------------------------------------------------------------- icon
def _build_icon() -> QIcon:
    """Draw a small chart icon programmatically so we ship no PNGs.

    Uses Microsoft blue accent to match the dashboard theme.
    """
    sizes = [16, 24, 32, 48, 64, 128, 256]
    icon = QIcon()
    for s in sizes:
        pm = QPixmap(s, s)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        # Rounded square background.
        margin = max(1, s // 16)
        rect = pm.rect().adjusted(margin, margin, -margin, -margin)
        p.setBrush(QBrush(QColor("#0078D4")))
        p.setPen(QPen(QColor("#005A9E"), max(1, s // 32)))
        p.drawRoundedRect(rect, s * 0.18, s * 0.18)
        # Three bars (chart glyph).
        bar_w = max(1, s // 8)
        gap = max(1, s // 16)
        base_y = int(s * 0.78)
        heights = [int(s * 0.25), int(s * 0.45), int(s * 0.62)]
        x = int(s * 0.22)
        for h in heights:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor("#FFFFFF")))
            p.drawRoundedRect(x, base_y - h, bar_w, h, max(1, s // 32), max(1, s // 32))
            x += bar_w + gap
        p.end()
        icon.addPixmap(pm)
    return icon


# ---------------------------------------------------------------- popup
class MiniPopup(QWidget):
    """A compact, always-on-top summary window (light theme)."""

    def __init__(self, controller: AppController):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self._controller = controller
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setWindowTitle("TokenPulse")
        self.resize(340, 240)
        self._build()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self._refresh()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("card")
        frame.setStyleSheet(
            """
            QFrame#card {
                background-color: #FFFFFF;
                border: 1px solid #EDEBE9;
                border-radius: 10px;
            }
            QLabel#title { color: #1F1F1F; font-size: 14px; font-weight: 600; }
            QLabel#sub   { color: #605E5C; font-size: 11px; }
            QLabel#val   { color: #1F1F1F; font-size: 22px; font-weight: 600; }
            QLabel#row   { color: #1F1F1F; font-size: 12px; }
            QProgressBar { background-color: #EDEBE9; border: none;
                           border-radius: 4px; text-align: center; color: #1F1F1F; }
            QProgressBar::chunk { background-color: #0078D4; border-radius: 4px; }
            """
        )
        outer.addWidget(frame)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Title row.
        title_row = QHBoxLayout()
        title = QLabel("TokenPulse")
        title.setObjectName("title")
        self.plan_label = QLabel("")
        self.plan_label.setObjectName("sub")
        self.plan_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self.plan_label)
        layout.addLayout(title_row)

        # Main number row.
        self.tokens_label = QLabel("—")
        self.tokens_label.setObjectName("val")
        layout.addWidget(self.tokens_label)

        self.sub_label = QLabel("")
        self.sub_label.setObjectName("sub")
        self.sub_label.setWordWrap(True)
        layout.addWidget(self.sub_label)

        # Secondary stats row.
        stats_row = QHBoxLayout()
        self.cost_label = QLabel("")
        self.cost_label.setObjectName("row")
        self.turns_label = QLabel("")
        self.turns_label.setObjectName("row")
        self.turns_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        stats_row.addWidget(self.cost_label)
        stats_row.addStretch(1)
        stats_row.addWidget(self.turns_label)
        layout.addLayout(stats_row)

        # Quota bars.
        self.bar5h = QProgressBar()
        self.bar5h.setRange(0, 100)
        self.bar5h.setValue(0)
        self.bar5h.setFormat("5小时 %p%")
        self.bar5h.setObjectName("ratePrimary")
        layout.addWidget(self.bar5h)

        self.bar7d = QProgressBar()
        self.bar7d.setRange(0, 100)
        self.bar7d.setValue(0)
        self.bar7d.setFormat("周 %p%")
        self.bar7d.setObjectName("rateSecondary")
        layout.addWidget(self.bar7d)

    def _refresh(self) -> None:
        storage = self._controller.storage()
        totals = storage.totals()
        rate = storage.latest_rate_limit()
        if totals.records == 0:
            self.tokens_label.setText("—")
            self.sub_label.setText("暂无数据，请启动 Codex 或 Claude Code")
            return
        self.tokens_label.setText(_humanize(totals.total_tokens))
        self.sub_label.setText(
            "%d 条记录 · 输入 %s · 输出 %s · 缓存 %s"
            % (
                totals.records,
                _humanize(totals.input_tokens),
                _humanize(totals.output_tokens),
                _humanize(totals.cache_read_tokens),
            )
        )
        self.cost_label.setText("费用：¥%.2f" % totals.cost)
        self.turns_label.setText("轮次：%d" % totals.interactions)
        if rate:
            self.plan_label.setText("套餐：%s" % (rate.plan_type or "—"))
            primary = rate.primary_used_percent or 0
            secondary = rate.secondary_used_percent or 0
            self.bar5h.setValue(int(primary))
            self.bar5h.setFormat("5小时 %.0f%%  ·  重置 %s" % (primary, _eta(rate.primary_resets_at)))
            self.bar7d.setValue(int(secondary))
            self.bar7d.setFormat("周 %.0f%%  ·  重置 %s" % (secondary, _eta(rate.secondary_resets_at)))
        else:
            self.plan_label.setText("")


def _humanize(n) -> str:
    n = float(n)
    for unit, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if abs(n) >= unit:
            return f"{n / unit:,.1f}{suffix}".replace(".0", "")
    return f"{n:,.0f}"


def _eta(ts_ms) -> str:
    if not ts_ms:
        return "—"
    import time
    delta_s = (ts_ms / 1000.0) - time.time()
    if delta_s <= 0:
        return "即将"
    if delta_s < 60:
        return f"{int(delta_s)} 秒"
    if delta_s < 3600:
        return f"{int(delta_s // 60)} 分钟"
    if delta_s < 86400:
        return f"{delta_s / 3600:.1f} 小时"
    return f"{delta_s / 86400:.1f} 天"


# ---------------------------------------------------------------- tray
class TrayIcon(QSystemTrayIcon):
    """Top-level tray icon that owns the MiniPopup."""

    show_window_requested = Signal()

    def __init__(self, controller: AppController, parent: Optional[QObject] = None):
        super().__init__(_build_icon(), parent)
        self._controller = controller
        self.setToolTip("TokenPulse 代理量监控")
        self._popup = None
        self._build_menu()
        self.activated.connect(self._on_activated)
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._refresh_tooltip)
        self._timer.start()
        self._refresh_tooltip()

    def _build_menu(self) -> None:
        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background-color: #FFFFFF; color: #1F1F1F;"
            "  border: 1px solid #EDEBE9; border-radius: 6px; padding: 4px; }"
            "QMenu::item { padding: 6px 18px; border-radius: 4px; }"
            "QMenu::item:selected { background-color: #DEECF9; color: #0078D4; }"
            "QMenu::separator { height: 1px; background: #EDEBE9; margin: 4px 6px; }"
        )
        show_action = QAction("打开 TokenPulse", self)
        show_action.triggered.connect(self.show_window_requested)
        menu.addAction(show_action)
        menu.addSeparator()
        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self._refresh_tooltip)
        menu.addAction(refresh_action)
        menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)
        self.setContextMenu(menu)

    @Slot(QSystemTrayIcon.ActivationReason)
    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._toggle_popup()

    def _toggle_popup(self) -> None:
        if self._popup is None or not self._popup.isVisible():
            self._popup = MiniPopup(self._controller)
            geo = self.geometry()
            screen = self.screen() or self._popup.screen()
            if screen is not None:
                scr = screen.availableGeometry()
                x = geo.x() if geo.x() > 0 else scr.right() - 360
                y = geo.y() - 250 if geo.y() > 260 else scr.bottom() - 250
                self._popup.move(x, y)
            self._popup.show()
        else:
            self._popup.hide()

    def _refresh_tooltip(self) -> None:
        storage = self._controller.storage()
        totals = storage.totals()
        rate = storage.latest_rate_limit()
        if totals.records == 0:
            self.setToolTip("TokenPulse — 等待首个事件…")
            return
        tip = "TokenPulse\n%s tokens · ¥%.2f · %d 轮次" % (
            _humanize(totals.total_tokens),
            totals.cost,
            totals.interactions,
        )
        if rate and rate.primary_used_percent is not None:
            tip += "\n5小时：%.0f%%  |  周：%.0f%%" % (
                rate.primary_used_percent,
                rate.secondary_used_percent or 0,
            )
        self.setToolTip(tip)

    def _quit_app(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()
