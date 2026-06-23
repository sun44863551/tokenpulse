"""One-click optimization dialog. Light PC-Manager theme matching the dashboard."""

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


# Light theme: soft tinted backgrounds with strong accent text.
SEVERITY_STYLE = {
    "high":   ("#FDE7E9", "#D13438", "⚠", "高"),
    "medium": ("#FFF4CE", "#866800", "⚡", "中"),
    "low":    ("#DEECF9", "#0078D4", "ℹ", "低"),
    "info":   ("#F3F2F1", "#605E5C", "•", "信息"),
}


def _wrap_tip(parent: QWidget, tip: OptimizationTip) -> QFrame:
    """Build a card-like row that shows the optimization plan + savings %.

    Layout: [icon+title+badge | detail | big saving circle]
    预估节省 token 百分比以大号字显示在右侧.
    """
    bg, fg, icon, label = SEVERITY_STYLE.get(tip.severity, SEVERITY_STYLE["info"])
    card = QFrame(parent)
    card.setObjectName("tipsDialogCard")
    card.setStyleSheet(
        "QFrame#tipsDialogCard {"
        "  background-color: %s;"
        "  border-radius: 10px;"
        "  border: 1px solid #EDEBE9;"
        "}" % bg
    )
    outer = QHBoxLayout(card)
    outer.setContentsMargins(14, 12, 14, 12)
    outer.setSpacing(14)

    # ===== 左侧: 优化方案 (标题 + 详情 + 规则) =====
    left = QVBoxLayout()
    left.setSpacing(6)
    left.setContentsMargins(0, 0, 0, 0)

    # 标题行: 图标 + 标题 + 优先级徽章
    title_row = QHBoxLayout()
    title_row.setSpacing(8)
    icon_label = QLabel(icon)
    icon_label.setStyleSheet(
        "color: %s; font-size: 18px; font-weight: 700; background: transparent;" % fg
    )
    icon_label.setFixedWidth(22)
    title_row.addWidget(icon_label, 0, Qt.AlignTop)
    title_label = QLabel(tip.title)
    title_label.setStyleSheet(
        "color: #1F1F1F; font-size: 14px; font-weight: 600; background: transparent;"
    )
    title_label.setWordWrap(True)
    title_row.addWidget(title_label, 1)
    badge = QLabel(label)
    badge.setAlignment(Qt.AlignCenter)
    badge.setFixedSize(40, 22)
    badge.setStyleSheet(
        "color: %s; font-size: 11px; font-weight: 700;"
        " background-color: rgba(0,0,0,0.04);"
        " border-radius: 11px;" % fg
    )
    title_row.addWidget(badge, 0, Qt.AlignTop)
    left.addLayout(title_row)

    # 优化方案详情
    detail_label = QLabel(tip.detail)
    detail_label.setWordWrap(True)
    detail_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    detail_label.setStyleSheet(
        "color: #1F1F1F; font-size: 12px; line-height: 1.4em;"
        " background: transparent;"
    )
    left.addWidget(detail_label)

    # 规则代码
    code_label = QLabel("规则代码: " + tip.code)
    code_label.setStyleSheet(
        "color: #8A8886; font-size: 11px; background: transparent;"
    )
    left.addWidget(code_label)
    left.addStretch(1)

    outer.addLayout(left, 1)

    # ===== 右侧: 预估节省百分比圈 =====
    if tip.saving_pct > 0:
        right = QFrame()
        right.setFixedWidth(112)
        right.setStyleSheet(
            "background-color: rgba(255,255,255,0.55);"
            " border: 1px solid rgba(16,124,16,0.25);"
            " border-radius: 10px;"
        )
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(6, 8, 6, 8)
        right_lay.setSpacing(0)
        right_lay.setAlignment(Qt.AlignCenter)

        pct_text = QLabel(f"{tip.saving_pct * 100:.0f}%")
        pct_font = QFont()
        pct_font.setPointSize(22)
        pct_font.setBold(True)
        pct_text.setFont(pct_font)
        pct_text.setAlignment(Qt.AlignCenter)
        pct_text.setStyleSheet(
            "color: #107C10; background: transparent; border: none;"
        )
        right_lay.addWidget(pct_text)

        sub_text = QLabel("预估节省 token")
        sub_text.setAlignment(Qt.AlignCenter)
        sub_text.setWordWrap(True)
        sub_text.setStyleSheet(
            "color: #605E5C; font-size: 10px; background: transparent; border: none;"
        )
        right_lay.addWidget(sub_text)

        outer.addWidget(right, 0, Qt.AlignVCenter)
    elif tip.saving:
        # 没有 saving_pct 时退而显示文本
        fallback = QLabel(tip.saving)
        fallback.setStyleSheet(
            "color: #107C10; font-size: 12px; font-weight: 600;"
            " background: transparent;"
        )
        fallback.setAlignment(Qt.AlignCenter)
        fallback.setMinimumWidth(112)
        outer.addWidget(fallback, 0, Qt.AlignVCenter)

    return card


class TipsDialog(QDialog):
    """Light-themed one-click optimization dialog."""

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
            "QDialog { background-color: #F3F3F3; color: #1F1F1F; }"
            " QScrollArea { background-color: #F3F3F3; border: none; }"
            " QWidget#tipsDialogScrollContent { background-color: #F3F3F3; }"
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
        title.setStyleSheet("color: #1F1F1F;")
        root.addWidget(title)

        subtitle = QLabel(summarise_tips(tips) if tips else "没有需要处理的问题。")
        subtitle.setStyleSheet("color: #605E5C; font-size: 12px;")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # ---- KPI strip: counts of high / medium / low
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)
        kpi_data = self._count_by_severity(tips)
        kpi_specs = [
            ("高优先级", kpi_data.get("high", 0), "#D13438", "#FDE7E9"),
            ("中优先级", kpi_data.get("medium", 0), "#866800", "#FFF4CE"),
            ("低优先级", kpi_data.get("low", 0), "#0078D4", "#DEECF9"),
        ]
        for label_text, count, color, bg in kpi_specs:
            kpi = QFrame()
            kpi.setStyleSheet(
                "background-color: %s; border-radius: 8px; border: 1px solid #EDEBE9;" % bg
            )
            kpi_lay = QVBoxLayout(kpi)
            kpi_lay.setContentsMargins(12, 8, 12, 8)
            kpi_lay.setSpacing(0)
            n = QLabel(str(count))
            n.setStyleSheet("color: %s; font-size: 18px; font-weight: 700; background: transparent;" % color)
            t = QLabel(label_text)
            t.setStyleSheet("color: #605E5C; font-size: 11px; background: transparent;")
            kpi_lay.addWidget(n)
            kpi_lay.addWidget(t)
            kpi_row.addWidget(kpi)

        # 总预估节省 token 百分比 (取最大值, 以优先级最高为准)
        max_saving = max((t.saving_pct for t in tips if t.saving_pct > 0), default=0.0)
        if max_saving > 0:
            savings_kpi = QFrame()
            savings_kpi.setStyleSheet(
                "background-color: #DFF6DD; border-radius: 8px; border: 1px solid #9BD89B;"
            )
            sk_lay = QVBoxLayout(savings_kpi)
            sk_lay.setContentsMargins(12, 8, 12, 8)
            sk_lay.setSpacing(0)
            sk_n = QLabel(f"{max_saving * 100:.0f}%")
            sk_n.setStyleSheet(
                "color: #107C10; font-size: 18px; font-weight: 700; background: transparent;"
            )
            sk_t = QLabel("总预估节省 token")
            sk_t.setStyleSheet(
                "color: #605E5C; font-size: 11px; background: transparent;"
            )
            sk_lay.addWidget(sk_n)
            sk_lay.addWidget(sk_t)
            kpi_row.addWidget(savings_kpi)
        # "All good" KPI when no tips
        if not tips:
            ok_kpi = QFrame()
            ok_kpi.setStyleSheet(
                "background-color: #DFF6DD; border-radius: 8px; border: 1px solid #EDEBE9;"
            )
            ok_lay = QVBoxLayout(ok_kpi)
            ok_lay.setContentsMargins(12, 8, 12, 8)
            ok_lay.setSpacing(0)
            ok_n = QLabel("✓")
            ok_n.setStyleSheet("color: #107C10; font-size: 18px; font-weight: 700; background: transparent;")
            ok_t = QLabel("使用状态良好")
            ok_t.setStyleSheet("color: #605E5C; font-size: 11px; background: transparent;")
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
                "background-color: #DFF6DD; border-radius: 8px; border: 1px solid #EDEBE9;"
            )
            ok_lay = QVBoxLayout(ok_card)
            ok_lay.setContentsMargins(14, 12, 14, 12)
            ok_text = QLabel(
                "未检测到明显的优化点。如果你想再次分析，可点击底部「重新分析」。"
            )
            ok_text.setWordWrap(True)
            ok_text.setStyleSheet(
                "color: #107C10; font-size: 13px; background: transparent;"
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
        export_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #0078D4; color: white; font-weight: 600;"
            "  border: none; border-radius: 6px; padding: 8px 14px;"
            "}"
            "QPushButton:hover { background-color: #106EBE; }"
            "QPushButton:pressed { background-color: #005A9E; }"
            "QPushButton:disabled { background-color: #C8C6C4; }"
        )
        export_btn.setEnabled(bool(tips))
        export_btn.clicked.connect(self._handle_export)
        footer.addWidget(export_btn)

        copy_btn = QPushButton("复制全部到剪贴板")
        copy_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #FFFFFF; color: #1F1F1F;"
            "  border: 1px solid #EDEBE9; border-radius: 6px; padding: 8px 14px;"
            "}"
            "QPushButton:hover { background-color: #F3F2F1; border-color: #0078D4; color: #0078D4; }"
            "QPushButton:disabled { color: #C8C6C4; }"
        )
        copy_btn.setEnabled(bool(tips))
        copy_btn.clicked.connect(self._handle_copy)
        footer.addWidget(copy_btn)

        footer.addStretch(1)

        reanalyze_btn = QPushButton("重新分析")
        reanalyze_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent; color: #605E5C;"
            "  border: 1px solid #EDEBE9; border-radius: 6px; padding: 8px 14px;"
            "}"
            "QPushButton:hover { color: #0078D4; border-color: #0078D4; }"
        )
        reanalyze_btn.clicked.connect(self.accept)
        footer.addWidget(reanalyze_btn)

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent; color: #1F1F1F;"
            "  border: 1px solid #EDEBE9; border-radius: 6px; padding: 8px 14px;"
            "}"
            "QPushButton:hover { border-color: #8A8886; }"
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
            _, _, _, label = SEVERITY_STYLE.get(t.severity, SEVERITY_STYLE["info"])
            lines.append(f"{i}. [{label}] {t.title}")
            lines.append(f"   规则: {t.code}")
            lines.append(f"   {t.detail}")
            if t.saving:
                lines.append(f"   节省估算: {t.saving}")
            lines.append("")
        return "\n".join(lines)
