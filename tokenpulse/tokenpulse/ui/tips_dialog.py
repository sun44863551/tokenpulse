"""一键优化对话框。展示全部优化建议，支持导出报告和复制全部。"""

from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.optimizer import summarise as summarise_tips
from ..core.models import OptimizationTip


SEVERITY_STYLE = {
    "high": ("#5a1d1d", "#ff7b72", "⚠", "高"),
    "medium": ("#5a3d1d", "#d29922", "⚡", "中"),
    "low": ("#1d3a5a", "#58a6ff", "ℹ", "低"),
    "info": ("#1d3a5a", "#8b949e", "•", "信息"),
}


def _wrap_tip(parent: QWidget, tip: OptimizationTip) -> QFrame:
    """Build a card-like row that shows the full tip (no truncation)."""
    bg, fg, icon, label = SEVERITY_STYLE.get(tip.severity, SEVERITY_STYLE["info"])
    card = QFrame(parent)
    card.setObjectName("tipsDialogCard")
    card.setStyleSheet(
        "QFrame#tipsDialogCard {"
        "  background-color: %s;"
        "  border-radius: 8px;"
        "  border: 1px solid #30363d;"
        "}"
        % bg
    )
    outer = QVBoxLayout(card)
    outer.setContentsMargins(14, 10, 14, 12)
    outer.setSpacing(6)

    # Title row: icon + title + severity badge + saving
    title_row = QHBoxLayout()
    title_row.setSpacing(8)
    icon_label = QLabel(icon)
    icon_label.setStyleSheet(
        "color: %s; font-size: 18px; font-weight: 600; background: transparent;" % fg
    )
    icon_label.setFixedWidth(22)
    title_row.addWidget(icon_label, 0, Qt.AlignTop)
    title_label = QLabel(tip.title)
    title_label.setStyleSheet(
        "color: #f0f6fc; font-size: 14px; font-weight: 600; background: transparent;"
    )
    title_label.setWordWrap(True)
    title_row.addWidget(title_label, 1)
    badge = QLabel(label)
    badge.setAlignment(Qt.AlignCenter)
    badge.setFixedSize(36, 20)
    badge.setStyleSheet(
        "color: %s; font-size: 11px; font-weight: 700;"
        " background-color: rgba(255,255,255,0.08);"
        " border-radius: 10px;" % fg
    )
    title_row.addWidget(badge, 0, Qt.AlignTop)
    if tip.saving:
        saving_label = QLabel(tip.saving)
        saving_label.setStyleSheet(
            "color: #7ee787; font-size: 12px; font-weight: 600;"
            " background: transparent;"
        )
        saving_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        title_row.addWidget(saving_label, 0, Qt.AlignTop)
    outer.addLayout(title_row)

    # Detail (full text, multi-line)
    detail_label = QLabel(tip.detail)
    detail_label.setWordWrap(True)
    detail_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    detail_label.setStyleSheet(
        "color: #c9d1d9; font-size: 12px; line-height: 1.4em;"
        " background: transparent;"
    )
    outer.addWidget(detail_label)

    # Code label (small, dim)
    code_label = QLabel("规则代码: " + tip.code)
    code_label.setStyleSheet(
        "color: #8b949e; font-size: 11px; background: transparent;"
    )
    outer.addWidget(code_label)

    return card


class TipsDialog(QDialog):
    """一键优化对话框。展示完整优化建议并提供导出/复制操作。"""

    def __init__(
        self,
        tips: List[OptimizationTip],
        on_export: Optional[Callable[[], None]] = None,
        on_copy: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._tips = tips
        self._on_export = on_export
        self._on_copy = on_copy
        self.setWindowTitle("TokenPulse · 一键优化")
        self.setModal(True)
        self.resize(720, 600)
        self.setMinimumSize(560, 420)
        self.setStyleSheet(
            "QDialog { background-color: #0d1117; color: #e6edf3; }"
            " QScrollArea { background-color: #0d1117; border: none; }"
            " QWidget#tipsDialogScrollContent { background-color: #0d1117; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        # ---- Header
        title = QLabel("一键优化")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #f0f6fc;")
        root.addWidget(title)

        subtitle = QLabel(summarise_tips(tips) if tips else "没有需要处理的问题。")
        subtitle.setStyleSheet("color: #8b949e; font-size: 12px;")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # ---- KPI strip: counts of high / medium / low
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)
        kpi_data = self._count_by_severity(tips)
        for sev_key, sev_label in (("high", "高优先级"), ("medium", "中优先级"), ("low", "低优先级")):
            n = kpi_data.get(sev_key, 0)
            bg, fg, _, _ = SEVERITY_STYLE[sev_key]
            kpi = QFrame()
            kpi.setStyleSheet(
                "QFrame { background-color: %s; border-radius: 8px; }" % bg
            )
            kpi.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            kpi_lay = QVBoxLayout(kpi)
            kpi_lay.setContentsMargins(12, 8, 12, 8)
            kpi_lay.setSpacing(2)
            n_label = QLabel(str(n))
            n_label.setStyleSheet(
                "color: #f0f6fc; font-size: 22px; font-weight: 700; background: transparent;"
            )
            sev_text = QLabel(sev_label)
            sev_text.setStyleSheet(
                "color: %s; font-size: 11px; background: transparent;" % fg
            )
            kpi_lay.addWidget(n_label)
            kpi_lay.addWidget(sev_text)
            kpi_row.addWidget(kpi)
        if not tips:
            ok_kpi = QFrame()
            ok_kpi.setStyleSheet(
                "QFrame { background-color: #0d4429; border-radius: 8px; }"
            )
            ok_lay = QVBoxLayout(ok_kpi)
            ok_lay.setContentsMargins(12, 8, 12, 8)
            ok_n = QLabel("✓")
            ok_n.setStyleSheet(
                "color: #7ee787; font-size: 22px; font-weight: 700; background: transparent;"
            )
            ok_t = QLabel("当前使用模式良好")
            ok_t.setStyleSheet(
                "color: #7ee787; font-size: 11px; background: transparent;"
            )
            ok_lay.addWidget(ok_n)
            ok_lay.addWidget(ok_t)
            kpi_row.addWidget(ok_kpi)
        root.addLayout(kpi_row)

        # ---- Scrollable list of tips
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setObjectName("tipsDialogScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 4, 0, 4)
        content_layout.setSpacing(8)
        if tips:
            for tip in tips:
                content_layout.addWidget(_wrap_tip(content, tip))
        else:
            ok_card = QFrame(content)
            ok_card.setStyleSheet(
                "background-color: #0d4429; border-radius: 8px;"
            )
            ok_lay = QVBoxLayout(ok_card)
            ok_lay.setContentsMargins(14, 12, 14, 12)
            ok_text = QLabel(
                "未检测到明显的优化点。如果你想再次分析，可点击底部「重新分析」。"
            )
            ok_text.setWordWrap(True)
            ok_text.setStyleSheet(
                "color: #7ee787; font-size: 13px; background: transparent;"
            )
            ok_lay.addWidget(ok_text)
            content_layout.addWidget(ok_card)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # ---- Footer
        footer = QHBoxLayout()
        footer.setSpacing(8)
        export_btn = QPushButton("导出 Markdown 报告")
        export_btn.setObjectName("primaryButton")
        export_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #1f6feb; color: white; font-weight: 600;"
            "  border: none; border-radius: 6px; padding: 8px 14px;"
            "}"
            "QPushButton:hover { background-color: #388bfd; }"
            "QPushButton:pressed { background-color: #1158c7; }"
        )
        export_btn.setEnabled(bool(tips))
        export_btn.clicked.connect(self._handle_export)
        footer.addWidget(export_btn)

        copy_btn = QPushButton("复制全部到剪贴板")
        copy_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #21262d; color: #c9d1d9;"
            "  border: 1px solid #30363d; border-radius: 6px; padding: 8px 14px;"
            "}"
            "QPushButton:hover { background-color: #30363d; color: #f0f6fc; }"
        )
        copy_btn.setEnabled(bool(tips))
        copy_btn.clicked.connect(self._handle_copy)
        footer.addWidget(copy_btn)

        footer.addStretch(1)

        reanalyze_btn = QPushButton("重新分析")
        reanalyze_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent; color: #8b949e;"
            "  border: 1px solid #30363d; border-radius: 6px; padding: 8px 14px;"
            "}"
            "QPushButton:hover { color: #f0f6fc; border-color: #58a6ff; }"
        )
        reanalyze_btn.clicked.connect(self.accept)
        footer.addWidget(reanalyze_btn)

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent; color: #c9d1d9;"
            "  border: 1px solid #30363d; border-radius: 6px; padding: 8px 14px;"
            "}"
            "QPushButton:hover { color: #f0f6fc; border-color: #8b949e; }"
        )
        close_btn.clicked.connect(self.reject)
        footer.addWidget(close_btn)
        root.addLayout(footer)

    def _count_by_severity(self, tips: List[OptimizationTip]) -> dict:
        out = {"high": 0, "medium": 0, "low": 0}
        for t in tips:
            if t.severity in out:
                out[t.severity] += 1
        return out

    def _handle_export(self) -> None:
        if self._on_export is not None:
            self._on_export()
        else:
            # Fallback: copy a plaintext summary to clipboard
            QApplication.clipboard().setText(summarise_tips(self._tips))

    def _handle_copy(self) -> None:
        if self._on_copy is not None:
            self._on_copy()
        else:
            text = self._format_plaintext()
            QApplication.clipboard().setText(text)

    def _format_plaintext(self) -> str:
        lines = ["TokenPulse 优化建议", ""]
        for i, t in enumerate(self._tips, 1):
            bg, _, _, label = SEVERITY_STYLE.get(t.severity, SEVERITY_STYLE["info"])
            lines.append(f"{i}. [{label}] {t.title}")
            lines.append(f"   规则: {t.code}")
            lines.append(f"   {t.detail}")
            if t.saving:
                lines.append(f"   节省估算: {t.saving}")
            lines.append("")
        return "\n".join(lines)
