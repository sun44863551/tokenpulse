"""
TokenPulse 一键预览脚本
=======================
- 启动主窗口并自动注入演示数据
- 适合不接 Codex / Claude Code 日志时快速查看 UI
- 截图保存到 docs/preview_*.png

用法:
    python preview.py                 # 启动 GUI 窗口(需要真实显示器)
    python preview.py --screenshot    # 生成三张截图后退出(适合 CI / 无头环境)
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time
from pathlib import Path

# 让脚本可以直接以 ``python preview.py`` 运行,无须安装包。
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _ensure_qt_app():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication
    # 注意: setHighDpiScaleFactorRoundingPolicy 必须在 QApplication 创建之前调用,
    # 否则会触发 Qt 警告并可能导致窗口无法正常显示。
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(sys.argv)
    # 加载系统中文字体,保证截图里中文正常显示。
    for font_path in (
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simsun.ttc",
    ):
        if Path(font_path).exists():
            QFontDatabase.addApplicationFont(font_path)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setApplicationName("TokenPulse")
    app.setOrganizationName("TokenPulse")
    return app


def _seed_demo_data(storage) -> None:
    """注入若干演示记录,这样图表与一键优化对话框都有内容。"""
    from tokenpulse.core.models import UsageRecord
    now = int(time.time() * 1000)
    samples = [
        ("codex", "gpt-5", 12000, 800, 8000, 0, 200, 0.10),
        ("codex", "gpt-5", 8500, 600, 6000, 0, 100, 0.07),
        ("codex", "gpt-5", 45000, 3000, 5000, 0, 0, 0.55),
        ("claude-code", "claude-sonnet-4-5", 18000, 2000, 10000, 0, 500, 0.16),
        ("codex", "gpt-5-mini", 5000, 300, 0, 0, 0, 0.005),
        ("claude-code", "claude-opus-4", 22000, 1500, 0, 0, 0, 0.45),
    ]
    for i, (tool, model, inp, out, cr, cw, thk, cost) in enumerate(samples):
        rec = UsageRecord(
            id=f"preview-demo-{i}",
            ts=now - i * 60000,
            tool=tool,
            model=model,
            input_tokens=inp,
            output_tokens=out,
            cache_read_tokens=cr,
            cache_write_tokens=cw,
            thinking_tokens=thk,
            cost=cost,
            session_id="preview-demo",
            source_file="preview-demo.jsonl",
        )
        storage.upsert_usage(rec)


def _pump(app, seconds: float = 0.6) -> None:
    """跑一小段时间的事件循环,让 Qt 完整布局与渲染。"""
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


def take_screenshots(out_dir: Path) -> list[Path]:
    """生成三张关键截图(主窗口 / 图表 / 优化对话框)。"""
    from tokenpulse.app import build_default_controller
    from tokenpulse.ui.main_window import MainWindow
    from tokenpulse.ui.high_perf_chart import HighPerfChart
    from tokenpulse.ui.tips_dialog import TipsDialog
    from tokenpulse.core.optimizer import run as run_optimizer
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    app = _ensure_qt_app()
    paths = []
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. 主窗口 -----------------------------------------------------------
    ctl = build_default_controller()
    _seed_demo_data(ctl.storage())
    win = MainWindow(ctl)
    win.resize(1280, 760)
    win.show()
    _pump(app, 0.8)
    p1 = out_dir / "preview_main_window.png"
    win.grab().save(str(p1), "PNG")
    win.close()

    # ---- 2. HighPerfChart 单独展示 -----------------------------------------
    holder = QWidget()
    holder.setStyleSheet("background:#F3F3F3;")
    holder.resize(820, 380)
    v = QVBoxLayout(holder)
    v.setContentsMargins(20, 20, 20, 20)
    title = QLabel("每分钟代用量（实时）   HighPerfChart · 1000 样本环形缓冲")
    title.setStyleSheet(
        "color:#201F1E; font-size:14px; font-weight:600; background:transparent;"
    )
    v.addWidget(title)
    chart = HighPerfChart(1000, 50, "tokens/min")
    v.addWidget(chart, 1)
    holder.show()
    _pump(app, 0.3)
    for i in range(400):
        val = 50000 + 30000 * math.sin(i * 0.04) + (i * 50 % 4000)
        chart.update_data(val)
    _pump(app, 0.6)  # 等定时器多刷几次,把数据画出来
    p2 = out_dir / "preview_high_perf_chart.png"
    holder.grab().save(str(p2), "PNG")
    holder.close()

    # ---- 3. 紧凑概览窗口（参考设计的暖色风格）---------
    from tokenpulse.ui.warm_dashboard import OverviewWindow
    overview = OverviewWindow(ctl.storage())
    overview.show()
    _pump(app, 0.6)
    p_overview = out_dir / "preview_overview_warm.png"
    overview.grab().save(str(p_overview), "PNG")
    overview.close()
    paths.append(p_overview)

    # ---- 4. 一键优化对话框 -----------------------------------------------------
    stats = ctl.storage().usage_stats()
    tips = run_optimizer(stats)
    dlg = TipsDialog(tips, parent=None)
    dlg.resize(900, 620)
    dlg.show()
    _pump(app, 0.6)
    p3 = out_dir / "preview_tips_dialog.png"
    dlg.grab().save(str(p3), "PNG")
    dlg.close()

    return paths


def run_gui() -> int:
    """正常模式:打开主窗口,事件循环。需要真实显示器。"""
    # 取消 offscreen 强制,使用原生窗口平台。
    os.environ.pop("QT_QPA_PLATFORM", None)
    app = _ensure_qt_app()
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from tokenpulse.app import build_default_controller
    from tokenpulse.ui.main_window import MainWindow
    ctl = build_default_controller()
    _seed_demo_data(ctl.storage())
    win = MainWindow(ctl)

    # 根据当前屏幕实际尺寸自适应,确保窗口完全填满屏幕,
    # 避免右侧或底部被其他窗口遮挡。
    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        avail = screen.availableGeometry()
        # 留 0 像素边距,完全占满;若希望有边距可改为 avail.width()-40
        win.resize(avail.width(), avail.height())
        win.move(avail.x(), avail.y())
    else:
        win.resize(1280, 760)

    win.show()
    # 强制置顶并激活,避免被其他应用窗口遮挡。
    win.raise_()
    win.activateWindow()
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(prog="tokenpulse-preview")
    parser.add_argument(
        "--screenshot",
        action="store_true",
        help="不打开 GUI,只生成 docs/preview_*.png 然后退出(适合无头环境)。",
    )
    args = parser.parse_args()
    if args.screenshot:
        paths = take_screenshots(ROOT / "docs")
        for p in paths:
            print(f"  saved -> {p}")
        return 0
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
