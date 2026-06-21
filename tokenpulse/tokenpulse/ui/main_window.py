"""QMainWindow that hosts the dashboard and a status bar."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStatusBar,
    QSystemTrayIcon,
)

from ..app import AppController
from ..core.config import discover_sources
from .dashboard import Dashboard
from .styles import QSS
from .tray import TrayIcon


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController, parent: Optional[QMainWindow] = None):
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("TokenPulse")
        self.resize(1280, 820)
        self.setMinimumSize(960, 640)
        self.setStyleSheet(QSS)

        self.dashboard = Dashboard(controller, self)
        self.setCentralWidget(self.dashboard)

        self._build_menu()
        self._build_status_bar()
        controller.sources_changed.connect(self._on_sources_changed)

        # System tray (only if the platform supports it).
        self._tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = TrayIcon(controller, self)
            self._tray.show_window_requested.connect(self._show_from_tray)
            self._tray.show()

    # ------------------------------------------------------------- UI build
    def _build_menu(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&File")
        view_menu = bar.addMenu("&View")
        if QSystemTrayIcon.isSystemTrayAvailable():
            hide_action = QAction("Hide to tray", self)
            hide_action.setShortcut(QKeySequence("Ctrl+H"))
            hide_action.triggered.connect(self.hide)
            view_menu.addAction(hide_action)
            show_tray = QAction("Show tray icon", self)
            show_tray.triggered.connect(self._show_from_tray)
            view_menu.addAction(show_tray)

        refresh_action = QAction("Refresh now", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self.dashboard._refresh_totals_from_storage)
        file_menu.addAction(refresh_action)

        rescan_action = QAction("Rescan logs", self)
        rescan_action.triggered.connect(self._rescan)
        file_menu.addAction(rescan_action)

        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = bar.addMenu("&Help")
        about = QAction("About TokenPulse", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _build_status_bar(self) -> None:
        bar = QStatusBar(self)
        self.setStatusBar(bar)
        self._source_label = QLabel("No sources")
        bar.addWidget(self._source_label, 1)
        self._stats_label = QLabel("0 records")
        bar.addPermanentWidget(self._stats_label)

    # --------------------------------------------------------------- close
    def closeEvent(self, event) -> None:
        """If a tray is available, hide instead of quitting on close."""
        if self._tray is not None and self._tray.isVisible():
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "TokenPulse",
                "Still running in the system tray. Right-click the icon to quit.",
                QSystemTrayIcon.Information,
                3000,
            )
            return
        super().closeEvent(event)

    @Slot()
    def _show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    # --------------------------------------------------------------- signals
    @Slot(list)
    def _on_sources_changed(self, sources) -> None:
        if not sources:
            self._source_label.setText("No log sources found")
            return
        parts = []
        for s in sources:
            parts.append(
                f"{s.label}: {s.file_count} file(s) @ {', '.join(s.paths)}"
            )
        self._source_label.setText("  ?  ".join(parts))

    @Slot()
    def _rescan(self) -> None:
        sources = discover_sources()
        self._controller.set_sources(sources)
        self._on_sources_changed(
            [
                type("S", (), {
                    "tool": s.tool,
                    "label": s.label,
                    "file_count": 0,
                    "paths": [str(p) for p in s.paths],
                })
                for s in sources
            ]
        )

    @Slot()
    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "TokenPulse",
            "TokenPulse v0.2.0\n\n"
            "Real-time, local-first token-usage visualizer for Codex, Claude Code, and other AI coding CLIs.\n\n"
            "All data stays on this machine.",
        )