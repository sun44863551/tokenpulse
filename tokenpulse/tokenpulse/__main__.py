"""Entry point: ``python -m tokenpulse`` or the ``tokenpulse`` script."""

from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from .app import build_default_controller
from .ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tokenpulse")
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="Run without showing the GUI (for headless smoke tests).",
    )
    parser.add_argument(
        "--tray-only",
        action="store_true",
        help="Start hidden in the system tray; do not show the main window.",
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Start with the main window minimized to the taskbar.",
    )
    args = parser.parse_args(argv)

    # Allow high-DPI rendering on Windows.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("TokenPulse")
    app.setOrganizationName("TokenPulse")

    # Use a font that supports Chinese characters on the host platform.
    from PySide6.QtGui import QFont, QFontDatabase
    fams = set(QFontDatabase.families())
    for cand in ("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans SC",
                 "PingFang SC", "Source Han Sans SC", "SimHei", "SimSun"):
        if cand in fams:
            f = QFont(cand, 10)
            app.setFont(f)
            break

    controller = build_default_controller()

    if args.no_window:
        # Allow the pipeline to run for a moment and then exit.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2500, app.quit)
        return app.exec()

    window = MainWindow(controller)
    if args.tray_only:
        window.hide()
    else:
        if args.minimized:
            window.showMinimized()
        else:
            # Robust bring-to-front: some hosts spawn the process in a
            # hidden window station or background session, which causes
            # ShowWindow to be rejected by the OS even though Qt thinks
            # the widget is visible. We force the window to the front
            # and schedule a second raise 200ms later to outlast any
            # focus-stealing that the IDE / shell might do.
            from PySide6.QtCore import QTimer
            window.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            window.show()
            window.raise_()
            window.activateWindow()
            window.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            window.show()
            window.raise_()
            window.activateWindow()
            QTimer.singleShot(200, window.raise_)
            QTimer.singleShot(200, window.activateWindow)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())