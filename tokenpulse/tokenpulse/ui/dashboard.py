"""仪表盘主窗体。包含简化后的 KPI 卡、实时折线图、模型饰饰图、工具列表和最近活动。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..app import AppController
from ..core.models import SourceStatus
from ..storage.db import Totals
from .charts import TimeSeriesChart, ModelPieChart


# ---------------------------------------------------------------- helpers
def _humanize(n) -> str:
    """将大数缩写为 K/M/B/T。"""
    n = float(n)
    for unit, suffix in [(1e12, "万亿"), (1e9, "亿"), (1e6, "万"), (1e3, "千")]:
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
        layout.setSpacing(4)
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

        # KPI 卡片（三个）
        self.total_card = _Card("总代理量")
        self.cost_card = _Card("预估费用")
        self.interactions_card = _Card("交互次数")
        self.interactions_card.sub_label.setText("本机会话日志统计")

        # 工具列表（右侧工具统计）
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

        # 图表
        self.chart = TimeSeriesChart()
        self.chart.setMinimumHeight(160)
        self.pie = ModelPieChart()
        self.pie.setMinimumHeight(180)
        self.pie.setSizePolicy(__import__("PySide6.QtWidgets", fromlist=["QSizePolicy"]).QSizePolicy.Preferred, __import__("PySide6.QtWidgets", fromlist=["QSizePolicy"]).QSizePolicy.Expanding)

        # 最近活动
        self.recent = QListWidget()
        self.recent.setMinimumHeight(140)

        self._build_layout()

        controller.new_usage.connect(self._on_new_usage)
        controller.new_interaction.connect(self._on_new_interaction)
        controller.stats_updated.connect(self._on_stats_updated)
        controller.interaction_plan_changed.connect(self._on_plan_changed)
        controller.sources_changed.connect(self._on_sources_changed)

        self._sync_sources_from_controller()
        self._refresh_totals_from_storage()

    # ---------------------------------------------------------------- layout
    def _build_layout(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        # 顶部标题行
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("TokenPulse")
        title.setObjectName("titleLabel")
        subtitle = QLabel("本地实时统计 Codex、Claude Code 等 AI 编程工具的 Token 使用量")
        subtitle.setObjectName("subtitleLabel")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self.plan_pill = QLabel("检测中…")
        self.plan_pill.setObjectName("pill")
        self.plan_pill.setVisible(False)
        header.addWidget(self.plan_pill, 0, Qt.AlignRight)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self._refresh_totals_from_storage)
        header.addWidget(self.refresh_button, 0, Qt.AlignRight)
        outer.addLayout(header)

        # KPI 行
        kpi_row = QGridLayout()
        kpi_row.setSpacing(10)
        kpi_row.addWidget(self.total_card, 0, 0)
        kpi_row.addWidget(self.cost_card, 0, 1)
        kpi_row.addWidget(self.interactions_card, 0, 2)
        for col in range(3):
            kpi_row.setColumnStretch(col, 1)
        outer.addLayout(kpi_row)

        # 实时折线图（全宽）
        chart_card = QFrame()
        chart_card.setObjectName("card")
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(14, 12, 14, 12)
        chart_title = QLabel("每分钟代理量（实时）")
        chart_title.setObjectName("cardTitle")
        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(self.chart)
        outer.addWidget(chart_card, stretch=3)

        # 二列：模型饰饰图 + 工具列表
        split_row = QHBoxLayout()
        split_row.setSpacing(14)

        pie_card = QFrame()
        pie_card.setObjectName("card")
        pie_layout = QVBoxLayout(pie_card)
        pie_layout.setContentsMargins(14, 12, 14, 12)
        pie_title = QLabel("按模型分布")
        pie_title.setObjectName("cardTitle")
        pie_layout.addWidget(pie_title)
        pie_layout.addWidget(self.pie)
        pie_card.setMinimumHeight(220)
        split_row.addWidget(pie_card, stretch=2)

        tools_card = QFrame()
        tools_card.setObjectName("card")
        tools_layout = QVBoxLayout(tools_card)
        tools_layout.setContentsMargins(14, 12, 14, 12)
        tools_title = QLabel("各工具统计")
        tools_title.setObjectName("cardTitle")
        tools_layout.addWidget(tools_title)
        tools_layout.addWidget(self.tool_scroll)
        tools_card.setMinimumHeight(220)
        split_row.addWidget(tools_card, stretch=3)

        outer.addLayout(split_row, stretch=4)

        # 最近活动（全宽）
        recent_card = QFrame()
        recent_card.setObjectName("card")
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(14, 12, 14, 12)
        r_title = QLabel("最近活动")
        r_title.setObjectName("cardTitle")
        recent_layout.addWidget(r_title)
        recent_layout.addWidget(self.recent)
        outer.addWidget(recent_card, stretch=2)

    # ------------------------------------------------------------------ slots
    @Slot(object)
    def _on_new_usage(self, record) -> None:
        # 推送点到实时图
        self.chart.add_point(record.tool, record.ts, record.total_tokens)
        # 插入最近活动
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

        # 5h 配额条
        rate_bar = QProgressBar()
        rate_bar.setRange(0, 100)
        rate_bar.setValue(0)
        rate_bar.setFormat("5小时用量 %p%")
        rate_bar.setObjectName("ratePrimary")
        layout.addWidget(rate_bar)

        # 周配额条
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
        # KPI 卡片
        self.total_card.value_label.setText(_humanize(totals.total_tokens))
        self.total_card.sub_label.setText(
            f"{totals.records:,} 条记录  ·  "
            f"输入 {_humanize(totals.input_tokens)}  ·  "
            f"输出 {_humanize(totals.output_tokens)}"
        )
        self.cost_card.value_label.setText(_format_money(totals.cost))
        self.cost_card.sub_label.setText(
            "按公开定价计算，缓存读取已折扣"
        )
        self.interactions_card.value_label.setText(f"{totals.interactions:,}")

        # 各工具卡片
        for tool, t in by_tool.items():
            card = self._tool_cards.get(tool)
            if card is None:
                continue
            card["value"].setText(_humanize(t.total_tokens))
            card["sub"].setText(
                f"{t.records:,} 条  ·  输入 {_humanize(t.input_tokens)}  ·  "
                f"输出 {_humanize(t.output_tokens)}  ·  {_format_money(t.cost)}"
            )

        # 5h / 周配额条
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

        # 模型饰饰图
        model_totals = {m: cats.get("total", 0) for m, cats in self._controller.storage().totals_by_model().items()}
        self.pie.set_data(model_totals)

    def _update_plan_pill(self) -> None:
        if not self._plan_type:
            self.plan_pill.setVisible(False)
            return
        self.plan_pill.setVisible(True)
        if self._interaction_plan:
            self.plan_pill.setText(f"套餐：{self._plan_type}  ·  按轮次计费")
            self.plan_pill.setObjectName("pillSuccess")
        else:
            self.plan_pill.setText(f"套餐：{self._plan_type}  ·  按token计费")
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
        """为控制器知道的每个源构建工具卡片。"""
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
