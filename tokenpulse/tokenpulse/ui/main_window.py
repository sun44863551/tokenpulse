"""QMainWindow that hosts the dashboard and a status bar."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMenu,
    QFileDialog,
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
        self.resize(1440, 960)
        self.setMinimumSize(1080, 720)
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
        file_menu = bar.addMenu("文件(&F)")
        view_menu = bar.addMenu("视图(&V)")
        if QSystemTrayIcon.isSystemTrayAvailable():
            hide_action = QAction("隐藏到托盘", self)
            hide_action.setShortcut(QKeySequence("Ctrl+H"))
            hide_action.triggered.connect(self.hide)
            view_menu.addAction(hide_action)
            show_tray = QAction("显示托盘图标", self)
            show_tray.triggered.connect(self._show_from_tray)
            view_menu.addAction(show_tray)

        refresh_action = QAction("立即刷新", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self.dashboard._refresh_totals_from_storage)
        file_menu.addAction(refresh_action)

        rescan_action = QAction("重新扫描日志", self)
        rescan_action.triggered.connect(self._rescan)
        file_menu.addAction(rescan_action)

        file_menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # 优化工具菜单
        tools_menu = bar.addMenu("优化(&O)")
        export_tips = QAction("导出优化报告为 Markdown", self)
        export_tips.setShortcut(QKeySequence("Ctrl+E"))
        export_tips.triggered.connect(self._export_optimization_report)
        tools_menu.addAction(export_tips)
        copy_summary = QAction("复制优化总结到剬贴板", self)
        copy_summary.triggered.connect(self._copy_optimization_summary)
        tools_menu.addAction(copy_summary)
        tools_menu.addSeparator()
        explain = QAction("如何阅读这些建议", self)
        explain.triggered.connect(self._show_optimization_help)
        tools_menu.addAction(explain)

        help_menu = bar.addMenu("帮助(&H)")
        about = QAction("关于 TokenPulse", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _build_status_bar(self) -> None:
        bar = QStatusBar(self)
        self.setStatusBar(bar)
        self._source_label = QLabel("未检测到日志源")
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
                "程序仍在后台运行，右键托盘选“退出”",
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
            self._source_label.setText("未检测到日志源，请检查 Codex 或 Claude Code")
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
            "TokenPulse v0.2.0 中文版\n\n"
            "本地实时统计 Codex、Claude Code 等 AI 编程工具的 Token 使用量。\n\n"
            "所有数据仅保存在本机。",
        )

    @Slot()
    def _export_optimization_report(self) -> None:
        "Export current optimization tips as Markdown."
        from PySide6.QtWidgets import QFileDialog
        from datetime import datetime
        from ..core.optimizer import run as run_optimizer, summarise
        storage = self._controller.storage()
        stats = storage.usage_stats()
        tips = run_optimizer(stats)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary = summarise(tips)
        sev_lbl = {"info": "信息", "low": "低", "medium": "中", "high": "高"}
        L = []
        L.append("# TokenPulse 优化报告")
        L.append("")
        L.append("生成时间: " + ts)
        L.append("")
        L.append("## 总体状态")
        L.append("")
        L.append(summary)
        L.append("")
        L.append("## 累计数据")
        L.append("")
        L.append("记录数: " + str(stats.records))
        L.append("总 Token: " + str(stats.total_input + stats.total_output + stats.total_cache_read))
        L.append("总花费: " + chr(0xffe5) + ("%.2f" % stats.total_cost))
        if stats.cache_hit_rate is not None:
            L.append("缓存命中率: " + ("%.1f%%" % (stats.cache_hit_rate*100)))
        if stats.interaction_count is not None:
            L.append("交互次数: " + str(stats.interaction_count))
        L.append("")
        L.append("## 按模型分布")
        L.append("")
        L.append("| 模型 | 提示 | 生成 | 缓存读 | 缓存写 | 思考 | 花费 |")
        L.append("|------|------:|------:|-------:|-------:|------:|------:|")
        for m_name, m in stats.by_model.items():
            cost = m["cost"] if m["cost"] is not None else 0.0
            L.append("| " + m_name + " | " + str(m["input"]) + " | " + str(m["output"]) + " | " + str(m["cache_read"]) + " | " + str(m["cache_write"]) + " | " + str(m["thinking"]) + " | " + chr(0xffe5) + ("%.2f" % cost) + " |")
        L.append("")
        L.append("## 优化建议")
        L.append("")
        if not tips:
            L.append("当前没有发现需要优化的问题。")
        else:
            for i, tip in enumerate(tips, 1):
                lvl = sev_lbl.get(tip.severity, "信息")
                L.append("### " + str(i) + ". [" + lvl + "] " + tip.title)
                L.append("")
                L.append("- 规则: " + tip.code)
                L.append("- 详情: " + tip.detail)
                if tip.saving:
                    L.append("- 节省估算: " + tip.saving)
                L.append("")
        content = chr(10).join(L)
        default_name = "tokenpulse-report-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".md"
        path_str, _f = QFileDialog.getSaveFileName(self, "导出优化报告", default_name, "Markdown 文件 (*.md);;所有文件 (*)")
        if not path_str:
            return
        try:
            with open(path_str, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            QMessageBox.warning(self, "导出失败", "无法写入文件: " + str(e))
            return
        self.statusBar().showMessage("已导出报告: " + path_str, 5000)
    @Slot()
    def _copy_optimization_summary(self) -> None:
        "Copy one-line summary of optimization tips to the clipboard."
        from PySide6.QtWidgets import QApplication
        from ..core.optimizer import run as run_optimizer, summarise
        storage = self._controller.storage()
        stats = storage.usage_stats()
        tips = run_optimizer(stats)
        summary = summarise(tips)
        QApplication.clipboard().setText(summary)
        self.statusBar().showMessage("已复制到剪贴板: " + summary, 4000)
    @Slot()
    def _show_optimization_help(self) -> None:
        "Show a help dialog explaining how to read the optimization tips."
        body = chr(10).join([
            chr(0x00b7) + " 缓存命中率较低 (low_cache_hit): [中] 命中率<20%, [低] <40%。Prompt 缓存可显著降低成本、建议在系统提示或工具说明中复用大段静态文本。",
            chr(0x00b7) + " 高价模型占比过高 (expensive_model_share): [中] 高价模型花费占比>85%。将简单任务路由到 mini/nano 模型可大幅降低账单。",
            chr(0x00b7) + " 提示词过大 (oversized_prompts): [中] 平均输入>30K, [低] >15K。考虑拆分上下文、压缩历史或使用 RAG 替代长粘贴。",
            chr(0x00b7) + " 单次请求过大 (oversized_single_request): 任意一次>100K 触发。建议拆分会话或外部存储。",
            chr(0x00b7) + " 输入/输出比例夸大 (input_heavy): [低] 输入/输出>95%。注意检查是否有重复粘贴大段历史。",
            chr(0x00b7) + " 思考消耗偏高 (thinking_heavy): [低] 思考>40%。扩展思考按思考 token 计费、注意控制。",
        ])
        QMessageBox.information(
            self,
            "如何阅读优化建议",
            "TokenPulse 的优化建议按严重度分为三档:[高] (深红)、[中] (深黄)、[低] (深蓝)，信息级不显示。"
            + chr(10) + chr(10) +
            "当前启用的规则:" + chr(10) + body
            + chr(10) + chr(10) +
            "提示:菜单 ·优化· 下可导出 Markdown 报告或复制单行总结。",
        )
