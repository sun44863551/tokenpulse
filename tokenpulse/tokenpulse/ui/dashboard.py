"""Dashboard main window. Microsoft PC Manager light theme: white cards, Microsoft blue accent, large rounded corners.

Layout uses a QScrollArea wrapper so widgets always get their natural
sizes and the hero card never gets squashed by the layout system.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..app import AppController
from ..core.models import SourceStatus
from ..storage.db import Totals
from .tips_dialog import TipsDialog
from .charts import TimeSeriesChart, ModelPieChart


# ---------------------------------------------------------------- helpers
def _html_escape(s) -> str:
    """Tiny HTML escape for rich-text labels."""
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _humanize(n) -> str:
    """Compress large numbers to K/M/B/T."""
    n = float(n)
    for unit, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if abs(n) >= unit:
            return f"{n / unit:,.1f}{suffix}".replace(".0", "")
    return f"{n:,.0f}"


def _format_money(amount: float) -> str:
    if amount >= 1:
        return f"¥{amount:,.2f}"
    if amount >= 0.01:
        return f"¥{amount:.3f}"
    return f"¥{amount:.4f}"


def _format_eta(ts_ms) -> str:
    if not ts_ms:
        return "—"
    delta_s = (ts_ms / 1000.0) - datetime.now().timestamp()
    if delta_s <= 0:
        return "即刷新"
    if delta_s < 60:
        return f"{int(delta_s)} 秒后"
    if delta_s < 3600:
        return f"{int(delta_s // 60)} 分钟后"
    if delta_s < 86400:
        return f"{delta_s / 3600:.1f} 小时后"
    return f"{delta_s / 86400:.1f} 天后"


def _format_time(ts_ms: int) -> str:
    if not ts_ms:
        return "—"
    return datetime.fromtimestamp(ts_ms / 1000.0).strftime("%H:%M:%S")


# ---------------------------------------------------------------- KPI card
class _Card(QFrame):
    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        self.value_label = QLabel("—")
        self.value_label.setObjectName("cardValue")
        self.sub_label = QLabel("")
        self.sub_label.setObjectName("cardSubValue")
        self.sub_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.sub_label)


# ---------------------------------------------------------------- dashboard
class Dashboard(QWidget):
    def __init__(self, controller: AppController, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("root")
        self._controller = controller
        self._interaction_plan = False
        self._plan_type: Optional[str] = None

        # --- hero status pill + main number + buttons
        self._hero_status_pill = QLabel("· 加载中")
        self._hero_status_pill.setObjectName("pill")
        self._hero_value = QLabel("—")
        self._hero_value.setObjectName("heroValue")
        self._hero_label = QLabel("Token 总用量")
        self._hero_label.setObjectName("heroLabel")
        self._hero_sub = QLabel("—")
        self._hero_sub.setObjectName("heroSub")
        self._hero_action_btn = QPushButton("一键优化")
        self._hero_action_btn.setObjectName("heroAction")
        self._hero_action_btn.setCursor(Qt.PointingHandCursor)
        self._hero_action_btn.clicked.connect(self._on_one_click_optimize)
        self._hero_export_btn = QPushButton("导出报告")
        self._hero_export_btn.setObjectName("heroActionSecondary")
        self._hero_export_btn.setCursor(Qt.PointingHandCursor)
        self._hero_export_btn.clicked.connect(self._invoke_export_report)
        self._hero_refresh_btn = QPushButton("刷新")
        self._hero_refresh_btn.setObjectName("heroActionSecondary")
        self._hero_refresh_btn.setCursor(Qt.PointingHandCursor)
        self._hero_refresh_btn.clicked.connect(self._refresh_totals_from_storage)

        # --- tool list
        self.tool_box = QVBoxLayout()
        self.tool_box.setContentsMargins(0, 0, 0, 0)
        self.tool_box.setSpacing(8)
        self.tool_holder = QWidget()
        self.tool_holder.setLayout(self.tool_box)
        self.tool_scroll = QScrollArea()
        self.tool_scroll.setWidgetResizable(True)
        self.tool_scroll.setWidget(self.tool_holder)
        self.tool_scroll.setFrameShape(QFrame.NoFrame)
        self._tool_cards: dict = {}

        # --- charts
        self.chart = TimeSeriesChart()
        self.chart.setMinimumHeight(180)
        self.pie = ModelPieChart()
        self.pie.setMinimumHeight(180)

        # --- recent activity
        self.recent = QListWidget()
        self.recent.setMinimumHeight(80)

        # Build all sub-widgets first (e.g. small stat cards),
        # then assemble the layout tree.
        self._build_widgets()
        self._build_layout()

        controller.new_usage.connect(self._on_new_usage)
        controller.new_interaction.connect(self._on_new_interaction)
        controller.stats_updated.connect(self._on_stats_updated)
        controller.interaction_plan_changed.connect(self._on_plan_changed)
        controller.sources_changed.connect(self._on_sources_changed)

        self._sync_sources_from_controller()
        self._refresh_totals_from_storage()

    # -------------------------------------------------------- widget factory
    def _build_widgets(self) -> None:
        """Create all card instances for the layout to consume."""
        # 4 small stat tiles
        self.cost_card = _Card("预估费用")
        self.cost_card.value_label.setStyleSheet("font-size: 22px; font-weight: 600;")
        self.interactions_card = _Card("交互次数")
        self.interactions_card.value_label.setStyleSheet("font-size: 22px; font-weight: 600;")
        self.interactions_card.sub_label.setText("本机会话日志统计")
        self.cache_card = _Card("缓存命中率")
        self.cache_card.value_label.setStyleSheet("font-size: 22px; font-weight: 600;")
        self.avg_card = _Card("平均输入")
        self.avg_card.value_label.setStyleSheet("font-size: 22px; font-weight: 600;")

        # tips list (lazy fill in _render_tips)
        self.tips_list = QVBoxLayout()
        self.tips_list.setContentsMargins(0, 0, 0, 0)
        self.tips_list.setSpacing(4)
        self._tip_widgets = []
        self.tips_summary = QLabel("加载中…")
        self.tips_summary.setObjectName("cardSubValue")

        # legacy KPI cards (kept for any external code paths, not shown).
        self.total_card = _Card("总代理量")
        self.total_card.setVisible(False)

    # ------------------------------------------------------------- layout
    def _build_layout(self) -> None:
        """Assemble the dashboard inside a QScrollArea so the hero card
        never gets squashed by the layout system."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        inner = QVBoxLayout(content)
        inner.setContentsMargins(20, 18, 20, 18)
        inner.setSpacing(14)

        # header (title + subtitle + plan pill)
        inner.addLayout(self._build_header())

        # hero card (fixed-height 180)
        inner.addWidget(self._build_hero_card())

        # 4 small stat tiles
        inner.addLayout(self._build_tiles_row())

        # real-time line chart
        inner.addWidget(self._build_chart_card())

        # pie + tools split
        inner.addLayout(self._build_split_row())

        # optimization tips
        inner.addWidget(self._build_tips_card())

        # recent activity
        inner.addWidget(self._build_recent_card())

        inner.addStretch(1)

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("TokenPulse")
        title.setObjectName("titleLabel")
        subtitle = QLabel("本地实时统计 Codex、Claude Code 等 AI 编程工具的 Token 使用量")
        subtitle.setObjectName("subtitleLabel")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)
        layout.addStretch(1)
        self.plan_pill = QLabel("检测中…")
        self.plan_pill.setObjectName("pill")
        self.plan_pill.setVisible(False)
        layout.addWidget(self.plan_pill, 0, Qt.AlignRight)
        return layout

    def _build_hero_card(self) -> QFrame:
        hero = QFrame()
        hero.setObjectName("heroCard")
        hero.setMinimumHeight(180)
        hero.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 16, 24, 16)
        hero_layout.setSpacing(10)

        # top row: status pill + three buttons on the right
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        self._hero_status_pill.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        top_row.addWidget(self._hero_status_pill, 0, Qt.AlignVCenter)
        top_row.addStretch(1)
        top_row.addWidget(self._hero_action_btn, 0, Qt.AlignVCenter)
        top_row.addSpacing(8)
        top_row.addWidget(self._hero_export_btn, 0, Qt.AlignVCenter)
        top_row.addSpacing(8)
        top_row.addWidget(self._hero_refresh_btn, 0, Qt.AlignVCenter)
        hero_layout.addLayout(top_row)

        # bottom row: label + value + sub info
        bot_row = QHBoxLayout()
        bot_row.setSpacing(16)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.addWidget(self._hero_label)
        text_col.addSpacing(2)
        text_col.addWidget(self._hero_value)
        text_col.addSpacing(4)
        text_col.addWidget(self._hero_sub)
        bot_row.addLayout(text_col, 1)
        bot_row.addStretch(0)
        hero_layout.addLayout(bot_row)
        return hero

    def _build_tiles_row(self) -> QHBoxLayout:
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        for c in (self.cost_card, self.interactions_card, self.cache_card, self.avg_card):
            tiles.addWidget(c, 1)
        return tiles

    def _build_chart_card(self) -> QFrame:
        chart_card = QFrame()
        chart_card.setObjectName("card")
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(18, 14, 18, 14)
        chart_title = QLabel("每分钟代理量（实时）")
        chart_title.setObjectName("cardTitle")
        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(self.chart)
        return chart_card

    def _build_split_row(self) -> QHBoxLayout:
        split_row = QHBoxLayout()
        split_row.setSpacing(14)

        pie_card = QFrame()
        pie_card.setObjectName("card")
        pie_layout = QVBoxLayout(pie_card)
        pie_layout.setContentsMargins(18, 14, 18, 14)
        pie_title = QLabel("按模型分布")
        pie_title.setObjectName("cardTitle")
        pie_layout.addWidget(pie_title)
        pie_layout.addWidget(self.pie)
        split_row.addWidget(pie_card, 2)

        tools_card = QFrame()
        tools_card.setObjectName("card")
        tools_layout = QVBoxLayout(tools_card)
        tools_layout.setContentsMargins(18, 14, 18, 14)
        tools_title = QLabel("各工具统计")
        tools_title.setObjectName("cardTitle")
        tools_layout.addWidget(tools_title)
        tools_layout.addWidget(self.tool_scroll, 1)
        split_row.addWidget(tools_card, 3)
        return split_row

    def _build_tips_card(self) -> QFrame:
        tips_card = QFrame()
        tips_card.setObjectName("card")
        tips_layout = QVBoxLayout(tips_card)
        tips_layout.setContentsMargins(18, 14, 18, 14)
        tips_layout.setSpacing(10)
        title_row = QHBoxLayout()
        tips_title = QLabel("优化建议")
        tips_title.setObjectName("cardTitle")
        title_row.addWidget(tips_title)
        title_row.addStretch(1)
        title_row.addWidget(self.tips_summary)
        title_row.addSpacing(10)
        self._one_click_btn = QPushButton("一键优化 →")
        self._one_click_btn.setObjectName("primaryButton")
        self._one_click_btn.setCursor(Qt.PointingHandCursor)
        self._one_click_btn.setToolTip("运行完整优化分析并打开对话框")
        self._one_click_btn.clicked.connect(self._on_one_click_optimize)
        title_row.addWidget(self._one_click_btn)
        tips_layout.addLayout(title_row)
        tips_layout.addLayout(self.tips_list)
        return tips_card

    def _build_recent_card(self) -> QFrame:
        recent_card = QFrame()
        recent_card.setObjectName("card")
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(18, 14, 18, 14)
        r_title = QLabel("最近活动")
        r_title.setObjectName("cardTitle")
        recent_layout.addWidget(r_title)
        recent_layout.addWidget(self.recent)
        return recent_card

    # ------------------------------------------------------------------ slots
    @Slot(object)
    def _on_new_usage(self, record) -> None:
        self.chart.add_point(record.tool, record.ts, record.total_tokens)
        item_text = (
            f"{_format_time(record.ts)}  ·  {record.tool}  ·  "
            f"{record.model or '—'}  ·  {_humanize(record.total_tokens)} tokens"
        )
        li = QListWidgetItem(item_text)
        self.recent.insertItem(0, li)
        if self.recent.count() > 30:
            self.recent.takeItem(self.recent.count() - 1)

    @Slot(object)
    def _on_new_interaction(self, record) -> None:
        totals = self._controller.storage().totals()
        self.interactions_card.value_label.setText(f"{totals.interactions:,}")

    @Slot(object, dict, object)
    def _on_stats_updated(self, totals: Totals, by_tool: dict, rate) -> None:
        self._render_totals(totals, by_tool, rate)
        self._render_tips()

    @Slot(bool, str)
    def _on_plan_changed(self, is_interaction_plan: bool, plan_type: str) -> None:
        self._interaction_plan = is_interaction_plan
        self._plan_type = plan_type or None
        self._update_plan_pill()
        if is_interaction_plan:
            self.interactions_card.title_label.setText("交互次数（计次付费）")
            self.interactions_card.sub_label.setText(
                f"订阅套餐 “{plan_type}” 按用户轮次计费"
            )
        else:
            self.interactions_card.title_label.setText("用户轮次")
            self.interactions_card.sub_label.setText("从本机会话日志统计")

    @Slot(list)
    def _on_sources_changed(self, sources) -> None:
        seen = set()
        for source in sources:
            self._ensure_tool_card(source)
            seen.add(source.tool)
        for tool in list(self._tool_cards.keys()):
            if tool not in seen:
                w = self._tool_cards.pop(tool)
                w["frame"].setParent(None)
                w["frame"].deleteLater()
        self._refresh_totals_from_storage()

    # ----------------------------------------------------------------- render
    def _ensure_tool_card(self, source: SourceStatus) -> None:
        if source.tool in self._tool_cards:
            return
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        title = QLabel(source.label)
        title.setObjectName("cardTitle")
        value = QLabel("0")
        value.setObjectName("cardValue")
        sub = QLabel(f"{source.file_count} 个日志文件")
        sub.setObjectName("cardSubValue")
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(sub)

        rate_bar = QProgressBar()
        rate_bar.setRange(0, 100)
        rate_bar.setValue(0)
        rate_bar.setFormat("5小时用量 %p%")
        rate_bar.setObjectName("ratePrimary")
        layout.addWidget(rate_bar)

        rate_bar_secondary = QProgressBar()
        rate_bar_secondary.setRange(0, 100)
        rate_bar_secondary.setValue(0)
        rate_bar_secondary.setFormat("周用量 %p%")
        rate_bar_secondary.setObjectName("rateSecondary")
        layout.addWidget(rate_bar_secondary)

        self.tool_box.addWidget(frame)
        self._tool_cards[source.tool] = {
            "frame": frame,
            "title": title,
            "value": value,
            "sub": sub,
            "rate_primary": rate_bar,
            "rate_secondary": rate_bar_secondary,
            "label": source.label,
        }

    def _render_totals(self, totals: Totals, by_tool: dict, rate) -> None:
        try:
            self._hero_value.setText(_humanize(totals.total_tokens))
            sub_parts = [
                str(totals.records) + " 条记录",
                "输入 " + _humanize(totals.input_tokens),
                "输出 " + _humanize(totals.output_tokens),
            ]
            if totals.cost > 0:
                sub_parts.append(_format_money(totals.cost))
            self._hero_sub.setText("  ·  ".join(sub_parts))
            self.cost_card.value_label.setText(_format_money(totals.cost))
            self.cost_card.sub_label.setText("按公开定价计算，缓存读取已折扣")
            self.interactions_card.value_label.setText(str(totals.interactions))
            plan_text = (
                "订阅套餐 \"" + (self._plan_type or "plus") + "\" "
                + ("按用户轮次计费" if self._interaction_plan else "不受计次限制")
            )
            self.interactions_card.sub_label.setText(plan_text)
            try:
                stats = self._controller.storage().usage_stats()
                if stats.cache_hit_rate is not None:
                    self.cache_card.value_label.setText(("%.1f%%" % (stats.cache_hit_rate * 100)))
                self.cache_card.sub_label.setText(
                    "读 " + _humanize(stats.total_cache_read)
                    + " / 输入 " + _humanize(stats.total_input)
                )
                self.avg_card.value_label.setText(_humanize(int(stats.avg_input_tokens)))
                self.avg_card.sub_label.setText("平均每次输入 token")
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.total_card.value_label.setText(_humanize(totals.total_tokens))
        except Exception:
            pass

        for tool, t in by_tool.items():
            card = self._tool_cards.get(tool)
            if card is None:
                continue
            card["value"].setText(_humanize(t.total_tokens))
            card["sub"].setText(
                f"{t.records:,} 条  ·  输入 {_humanize(t.input_tokens)}  ·  "
                f"输出 {_humanize(t.output_tokens)}  ·  {_format_money(t.cost)}"
            )

        if rate is not None and rate.tool in self._tool_cards:
            card = self._tool_cards[rate.tool]
            primary = rate.primary_used_percent or 0
            secondary = rate.secondary_used_percent or 0
            card["rate_primary"].setValue(int(primary))
            card["rate_primary"].setFormat(
                f"5小时 {primary:.0f}%  ·  重置 {_format_eta(rate.primary_resets_at)}"
            )
            if primary >= 90:
                card["rate_primary"].setObjectName("danger")
            elif primary >= 70:
                card["rate_primary"].setObjectName("warning")
            else:
                card["rate_primary"].setObjectName("ratePrimary")
            card["rate_primary"].style().unpolish(card["rate_primary"])
            card["rate_primary"].style().polish(card["rate_primary"])

            card["rate_secondary"].setValue(int(secondary))
            card["rate_secondary"].setFormat(
                f"周 {secondary:.0f}%  ·  重置 {_format_eta(rate.secondary_resets_at)}"
            )
            if secondary >= 90:
                card["rate_secondary"].setObjectName("danger")
            elif secondary >= 70:
                card["rate_secondary"].setObjectName("warning")
            else:
                card["rate_secondary"].setObjectName("rateSecondary")
            card["rate_secondary"].style().unpolish(card["rate_secondary"])
            card["rate_secondary"].style().polish(card["rate_secondary"])

        try:
            model_totals = {
                m: cats.get("total", 0)
                for m, cats in self._controller.storage().totals_by_model().items()
            }
            self.pie.set_data(model_totals)
        except Exception:
            pass

    def _render_tips(self) -> None:
        from ..core.optimizer import run as run_optimizer, summarise
        stats = self._controller.storage().usage_stats()
        tips = run_optimizer(stats)
        for w in self._tip_widgets:
            w.setParent(None)
            w.deleteLater()
        self._tip_widgets.clear()
        while self.tips_list.count():
            item = self.tips_list.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if not tips:
            self.tips_summary.setText("优化状态：良好")
            row = QFrame()
            row.setStyleSheet("background-color: #DFF6DD; border-radius: 6px;")
            box = QVBoxLayout(row)
            box.setContentsMargins(12, 8, 12, 8)
            t = QLabel("✅ 当前使用模式看起来不错，未检测到明显的优化点。")
            t.setWordWrap(True)
            t.setStyleSheet("color: #107C10; font-size: 12px;")
            box.addWidget(t)
            self.tips_list.addWidget(row)
            self._tip_widgets.append(row)
            self._set_hero_pill("good")
            return
        self.tips_summary.setText(summarise(tips))
        for tip in tips[:6]:
            row = self._build_tip_row(tip)
            self.tips_list.addWidget(row)
            self._tip_widgets.append(row)
        try:
            from ..core.optimizer import TIP_HIGH, TIP_MEDIUM
            high_n = sum(1 for t in tips if t.severity == TIP_HIGH)
            med_n = sum(1 for t in tips if t.severity == TIP_MEDIUM)
            if high_n:
                self._set_hero_pill("danger", f"{high_n} 条高优先级")
            elif med_n:
                self._set_hero_pill("warning", f"{med_n} 条中优先级")
            else:
                self._set_hero_pill("good", "使用状态良好")
        except Exception:
            pass

    def _set_hero_pill(self, kind: str, text: str = "") -> None:
        names = {"good": "pillSuccess", "warning": "pillWarning", "danger": "pillDanger", "info": "pill"}
        name = names.get(kind, "pill")
        self._hero_status_pill.setObjectName(name)
        if text:
            self._hero_status_pill.setText("· " + text)
        self._hero_status_pill.style().unpolish(self._hero_status_pill)
        self._hero_status_pill.style().polish(self._hero_status_pill)

    def _build_tip_row(self, tip) -> QFrame:
        # Light-theme palette: soft tinted backgrounds with strong accent text.
        colors = {
            "high": ("#FDE7E9", "#D13438", "⚠"),
            "medium": ("#FFF4CE", "#866800", "⚡"),
            "low": ("#DEECF9", "#0078D4", "ℹ"),
            "info": ("#F3F2F1", "#605E5C", "•"),
        }
        bg, fg, icon = colors.get(tip.severity, colors["info"])
        row = QFrame()
        row.setStyleSheet("background-color: %s; border-radius: 6px;" % bg)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.setMinimumHeight(44)
        box = QHBoxLayout(row)
        box.setContentsMargins(10, 4, 10, 4)
        box.setSpacing(10)
        badge = QLabel(icon)
        badge.setStyleSheet("color: %s; font-size: 16px; font-weight: 600; background: transparent;" % fg)
        badge.setFixedWidth(24)
        box.addWidget(badge, 0, Qt.AlignTop)
        first_line = tip.detail.split("\n", 1)[0]
        if len(first_line) > 80:
            first_line = first_line[:78] + "..."
        text_label = QLabel(tip.title + "  —  " + first_line)
        text_label.setStyleSheet("color: #1F1F1F; font-size: 12px; font-weight: 500; background: transparent;")
        text_label.setWordWrap(False)
        text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box.addWidget(text_label, 1)
        if tip.saving:
            saving_label = QLabel(tip.saving)
            saving_label.setStyleSheet("color: #107C10; font-size: 11px; background: transparent; font-weight: 600;")
            saving_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            saving_label.setFixedWidth(110)
            box.addWidget(saving_label, 0, Qt.AlignTop)
        return row

    @Slot()
    def _invoke_export_report(self) -> None:
        win = self.window()
        fn = getattr(win, "_export_optimization_report", None)
        if fn is not None:
            fn()
        else:
            from PySide6.QtWidgets import QApplication
            from ..core.optimizer import run as run_optimizer, summarise
            stats = self._controller.storage().usage_stats()
            tips = run_optimizer(stats)
            QApplication.clipboard().setText(summarise(tips))

    @Slot()
    def _on_one_click_optimize(self) -> None:
        from ..core.optimizer import run as run_optimizer
        stats = self._controller.storage().usage_stats()
        tips = run_optimizer(stats)
        self._render_tips()
        win = self.window()
        on_export = getattr(win, "_export_optimization_report", None)
        on_copy = getattr(win, "_copy_optimization_summary", None)
        dlg = TipsDialog(tips, on_export=on_export, on_copy=on_copy, parent=win)
        dlg.exec()

    def _update_plan_pill(self) -> None:
        if not self._plan_type:
            self.plan_pill.setVisible(False)
            return
        self.plan_pill.setVisible(True)
        if self._interaction_plan:
            self.plan_pill.setText(f"套餐：{self._plan_type}  ·  按轮次计费")
            self.plan_pill.setObjectName("pillSuccess")
        else:
            self.plan_pill.setText(f"套餐：{self._plan_type}  ·  按 token 计费")
            self.plan_pill.setObjectName("pill")
        self.plan_pill.style().unpolish(self.plan_pill)
        self.plan_pill.style().polish(self.plan_pill)

    def _refresh_totals_from_storage(self) -> None:
        storage = self._controller.storage()
        totals = storage.totals()
        by_tool = storage.totals_by_tool()
        rate = storage.latest_rate_limit()
        self._render_totals(totals, by_tool, rate)
        if rate and rate.plan_type:
            self._on_plan_changed(
                self._controller.is_interaction_plan(),
                rate.plan_type,
            )

    def _sync_sources_from_controller(self) -> None:
        import os
        statuses = []
        for s in self._controller.sources():
            file_count = 0
            for p in s.paths:
                if p.is_file():
                    file_count += 1
                elif p.is_dir():
                    for root, _, files in os.walk(p):
                        for f in files:
                            if f.endswith(".jsonl"):
                                file_count += 1
            statuses.append(
                SourceStatus(
                    tool=s.tool,
                    label=s.label,
                    paths=[str(x) for x in s.paths],
                    file_count=file_count,
                    active=True,
                )
            )
        self._on_sources_changed(statuses)
