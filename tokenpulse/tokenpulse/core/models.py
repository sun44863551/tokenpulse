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
    # Codex rate_limits metadata (newer Codex CLI populates these even when
    # primary/secondary are null, e.g. for non-OpenAI models like MiniMax-M3).
    limit_id: Optional[str] = None
    limit_name: Optional[str] = None
    credits_has_credits: Optional[bool] = None
    credits_unlimited: Optional[bool] = None
    credits_balance: Optional[str] = None
    individual_limit: Optional[str] = None
    rate_limit_reached_type: Optional[str] = None

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
    """Latest quota snapshot for one tool/plan.

    ``has_quota_data`` is the most important UI-facing flag: it is True
    only when Codex actually returned something usable (e.g. primary
    ``used_percent`` or a non-null ``rate_limit_reached_type``).  When
    the user is talking to a third-party model such as MiniMax-M3 the
    Codex backend reports the entire ``rate_limits`` block as null, so
    the UI must avoid rendering bogus 0% bars.
    """

    tool: str
    plan_type: Optional[str]
    primary_used_percent: Optional[float]
    primary_resets_at: Optional[int]
    secondary_used_percent: Optional[float]
    secondary_resets_at: Optional[int]
    limit_id: Optional[str] = None
    limit_name: Optional[str] = None
    credits_has_credits: Optional[bool] = None
    credits_unlimited: Optional[bool] = None
    credits_balance: Optional[str] = None
    individual_limit: Optional[str] = None
    rate_limit_reached_type: Optional[str] = None
    ts: int = 0

    @property
    def has_quota_data(self) -> bool:
        """True if Codex returned any meaningful quota information."""
        if self.primary_used_percent is not None:
            return True
        if self.secondary_used_percent is not None:
            return True
        if self.rate_limit_reached_type:
            return True
        if self.individual_limit:
            return True
        if self.credits_has_credits or self.credits_unlimited:
            return True
        return False


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
    saving: str = ""  # estimated saving ("~楼X/turn", "~30%浣?)
    saving_pct: float = 0.0  # estimated token savings ratio, 0-1 (0.3 = 30%)

    def rank(self) -> int:
        return _TIP_RANK.get(self.severity, 0)
