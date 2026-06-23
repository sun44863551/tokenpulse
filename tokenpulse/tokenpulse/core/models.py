"""Domain models used by parsers, storage, and UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UsageRecord:
    """One parsed token-count snapshot from a tool's log stream."""

    id: str
    ts: int  # unix millis
    tool: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    thinking_tokens: int = 0
    cost: float = 0.0
    session_id: Optional[str] = None
    source_file: str = ""
    # Codex only - quota snapshot taken at parse time.
    plan_type: Optional[str] = None
    primary_used_percent: Optional[float] = None
    primary_resets_at: Optional[int] = None
    secondary_used_percent: Optional[float] = None
    secondary_resets_at: Optional[int] = None

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
            + self.thinking_tokens
        )

    @property
    def billed_tokens(self) -> int:
        """Tokens that count against a pay-as-you-go bill (no cached reads)."""
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_write_tokens
            + self.thinking_tokens
        )


@dataclass
class InteractionRecord:
    """One user turn, used for "token plan" interaction counting."""

    id: str
    ts: int
    tool: str
    session_id: str
    source_file: str
    plan_type: Optional[str] = None


@dataclass
class RateLimitSnapshot:
    """Latest quota snapshot for one tool/plan."""

    tool: str
    plan_type: Optional[str]
    primary_used_percent: Optional[float]
    primary_resets_at: Optional[int]
    secondary_used_percent: Optional[float]
    secondary_resets_at: Optional[int]
    ts: int


@dataclass
class SourceStatus:
    """Whether a log source has been located and is being watched."""

    tool: str
    label: str
    paths: list[str]
    file_count: int = 0
    error: Optional[str] = None
    active: bool = False


# ---------------------------------------------------------------- optimization
# Severity levels for optimization tips, in increasing order of urgency.
TIP_INFO = "info"
TIP_LOW = "low"
TIP_MEDIUM = "medium"
TIP_HIGH = "high"

_TIP_RANK = {TIP_INFO: 0, TIP_LOW: 1, TIP_MEDIUM: 2, TIP_HIGH: 3}


@dataclass
class OptimizationTip:
    """One actionable suggestion produced by the optimizer."""

    severity: str  # one of TIP_INFO / TIP_LOW / TIP_MEDIUM / TIP_HIGH
    code: str      # short machine identifier, e.g. "low_cache_hit"
    title: str     # one-line summary, Chinese
    detail: str    # 1-2 sentence explanation, Chinese
    saving: str = ""  # estimated saving ("~¥X/turn", "~30%位")
    saving_pct: float = 0.0  # estimated token savings ratio, 0-1 (0.3 = 30%)

    def rank(self) -> int:
        return _TIP_RANK.get(self.severity, 0)
