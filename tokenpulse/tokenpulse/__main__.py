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
    args = parser.parse_args(argv)

    # Allow high-DPI rendering on Windows.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("TokenPulse")
    app.setOrganizationName("TokenPulse")

    controller = build_default_controller()

    if args.no_window:
        # Allow the pipeline to run for a moment and then exit.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2500, app.quit)
        return app.exec()

    window = MainWindow(controller)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())