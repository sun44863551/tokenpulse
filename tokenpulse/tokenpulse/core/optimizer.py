"""Heuristic rules that turn raw token usage into actionable tips.

Each rule inspects an :class:`UsageStats` snapshot (computed by
``Storage.usage_stats``) and may push one or more
:class:`tokenpulse.core.models.OptimizationTip` objects into the result
list.  Rules are pure functions; the ``Optimizer`` orchestrator is
responsible for ranking and limiting the output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from .models import (
    OptimizationTip,
    TIP_INFO,
    TIP_LOW,
    TIP_MEDIUM,
    TIP_HIGH,
)


@dataclass
class UsageStats:
    """Snapshot of aggregate usage used by the optimizer rules."""

    records: int = 0
    total_input: int = 0
    total_output: int = 0
    total_cache_read: int = 0
    total_cache_write: int = 0
    total_thinking: int = 0
    total_billed: int = 0
    total_cost: float = 0.0
    # Per-model breakdown: {model: {"input": int, "output": int, "cache_read": int, "cost": float}}
    by_model: dict = None  # type: ignore[assignment]
    # Largest single record (input+output) seen, and the corresponding model.
    max_request_tokens: int = 0
    max_request_model: str = ""
    # Average request size.
    avg_request_tokens: float = 0.0
    # Average input size (used to flag oversized prompts).
    avg_input_tokens: float = 0.0
    # Aggregate cache hit rate (cache_read / total_billed), 0..1.
    cache_hit_rate: float = 0.0
    # Number of recorded interactions (turn-level; only meaningful for interaction plans).
    interaction_count: int = 0

    def __post_init__(self):
        if self.by_model is None:
            self.by_model = {}


# Each rule is ``(name, fn)``; fn returns a list of tips.
RuleFn = Callable[[UsageStats], List[OptimizationTip]]


def _rule_low_cache_hit(s: UsageStats) -> List[OptimizationTip]:
    inp = s.total_input + s.total_cache_read
    if inp <= 10_000:
        return []  # not enough data
    rate = s.total_cache_read / max(1, inp)
    if rate < 0.20:
        return [OptimizationTip(
            severity=TIP_MEDIUM,
            code="low_cache_hit",
            title="缓存命中率较低",
            detail="当前仅 %.0f%% 的输入是从缓存读取的，可以把稳定的 system prompt 左右提取出来作为缓存前缀，预计能节省 30%%-50%% 的输入费用。" % (rate * 100),
            saving="~节省 30% 输入",
            saving_pct=0.30,
        )]
    if rate < 0.40:
        return [OptimizationTip(
            severity=TIP_LOW,
            code="low_cache_hit",
            title="缓存利用率有提升空间",
            detail="缓存读取占比 %.0f%%，如果会话中存在长且重复的上下文，可以尝试调整结构以提高缓存命中。" % (rate * 100),
            saving="~10% 位",
            saving_pct=0.10,
        )]
    return []


def _rule_expensive_model_share(s: UsageStats) -> List[OptimizationTip]:
    if not s.by_model:
        return []
    expensive_keywords = ("gpt-5.5", "gpt-5.4", "opus", "gpt-4o", "sonnet")
    expensive_total = 0
    grand_total = 0
    expensive_models = []
    for model, cats in s.by_model.items():
        billed = cats.get("input", 0) + cats.get("output", 0) + cats.get("cache_write", 0) + cats.get("thinking", 0)
        grand_total += billed
        if any(k in model.lower() for k in expensive_keywords):
            expensive_total += billed
            expensive_models.append(model)
    if grand_total < 50_000:
        return []
    share = expensive_total / max(1, grand_total)
    if share > 0.85 and len(s.by_model) >= 2:
        return [OptimizationTip(
            severity=TIP_MEDIUM,
            code="expensive_model_share",
            title="高价模型占比过高",
            detail="%.0f%% 的计费 token 来自高价模型，如果部分任务仅为代码检查、文本汇总等场景，可以切到 mini 型号，预计可节省 80% 以上费用。" % (share * 100),
            saving="~节省 80% 费用",
            saving_pct=0.80,
        )]
    return []


def _rule_oversized_prompts(s: UsageStats) -> List[OptimizationTip]:
    if s.records < 5:
        return []
    if s.avg_input_tokens > 30_000:
        return [OptimizationTip(
            severity=TIP_MEDIUM,
            code="oversized_prompts",
            title="平均输入偏高",
            detail="平均每次请求的输入达 %.1fK tokens，这上限可能会拖慢响应且推高费用。建议拆分任务、减少输入中的不必要上下文，或者使用期望仅供参考的外部文档。" % (s.avg_input_tokens / 1000),
            saving="~40% 位",
            saving_pct=0.40,
        )]
    if s.avg_input_tokens > 15_000:
        return [OptimizationTip(
            severity=TIP_LOW,
            code="oversized_prompts",
            title="输入轻微偏多",
            detail="平均输入 %.1fK tokens，如果中有大量重复上下文可以考虑汇总到 system prompt 缓存。" % (s.avg_input_tokens / 1000),
            saving="~20% 位",
            saving_pct=0.20,
        )]
    return []


def _rule_oversized_single_request(s: UsageStats) -> List[OptimizationTip]:
    if s.max_request_tokens <= 100_000:
        return []
    return [OptimizationTip(
        severity=TIP_HIGH,
        code="oversized_single_request",
        title="存在单次超大请求",
        detail="最大一次请求达 %.0fK tokens (%s)，这个任务可能可以拆分成多次调用。超长上下文不仅明显推高费用，还会使模型聊上下文失去重点。" % (s.max_request_tokens / 1000, s.max_request_model or "未知模型"),
        saving="~50% 位",
        saving_pct=0.50,
    )]


def _rule_high_input_output_ratio(s: UsageStats) -> List[OptimizationTip]:
    """If input is > 95%% of billed, the model is being used as a search engine."""
    billed = s.total_billed
    if billed < 50_000:
        return []
    inp = s.total_input + s.total_cache_write
    rate = inp / max(1, billed)
    if rate > 0.95:
        return [OptimizationTip(
            severity=TIP_LOW,
            code="input_heavy",
            title="输入/输出比例夸大",
            detail="输入占计费总额 %.0f%%，输出仅 %.0f%%，这意味着上下文很长但产出较少。如果是查询代码库，可以考虑先用 grep / ripgrep 在本地筛选，只把匹配到的上下文送给模型。" % (rate * 100, 100 - rate * 100),
            saving="~30% 位",
            saving_pct=0.30,
        )]
    return []


def _rule_low_thinking_ratio(s: UsageStats) -> List[OptimizationTip]:
    """If thinking tokens dominate, the task may be too complex for current model."""
    billed = s.total_billed
    if billed < 50_000:
        return []
    rate = s.total_thinking / max(1, billed)
    if rate > 0.40:
        return [OptimizationTip(
            severity=TIP_LOW,
            code="thinking_heavy",
            title="思考消耗偏高",
            detail="“思考”占计费总额 %.0f%%。如果任务不需要深度推理（如简单代码完型、代码格式化），可以关闭 reasoning 或选择轻量级模型。" % (rate * 100),
            saving="~25% 位",
            saving_pct=0.25,
        )]
    return []


DEFAULT_RULES: List[RuleFn] = [
    _rule_low_cache_hit,
    _rule_expensive_model_share,
    _rule_oversized_prompts,
    _rule_oversized_single_request,
    _rule_high_input_output_ratio,
    _rule_low_thinking_ratio,
]


def run(stats: UsageStats, rules: List[RuleFn] = None) -> List[OptimizationTip]:
    """Run all rules and return tips sorted by severity (high first)."""
    rules = rules or DEFAULT_RULES
    out: List[OptimizationTip] = []
    for fn in rules:
        try:
            out.extend(fn(stats))
        except Exception:
            # Never let a bad rule crash the UI.
            continue
    out.sort(key=lambda t: -t.rank())
    return out


def summarise(tips: List[OptimizationTip]) -> str:
    """One-line summary used by the tray popup."""
    if not tips:
        return "优化建议：暂无"
    high = sum(1 for t in tips if t.severity == TIP_HIGH)
    med = sum(1 for t in tips if t.severity == TIP_MEDIUM)
    if high:
        return "优化建议：%d 条高优先" % high
    if med:
        return "优化建议：%d 条可优化" % med
    return "优化建议：%d 条小建议" % len(tips)
