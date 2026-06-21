"""Lightweight pricing for the most common OpenAI / Anthropic models.

Values are USD per 1M tokens.  Cache reads typically get a 90% discount,
cache writes are billed at the input rate.  When a model is unknown we
return 0 so the UI still works."""

from __future__ import annotations

from typing import TypedDict


class ModelPricing(TypedDict, total=False):
    input: float
    output: float
    cache_read: float
    cache_write: float
    thinking: float  # defaults to output if absent


# Last updated 2025-2026 public list prices.
_PRICING: dict[str, ModelPricing] = {
    # OpenAI
    "gpt-5": {"input": 1.25, "output": 10.0, "cache_read": 0.125},
    "gpt-5-mini": {"input": 0.25, "output": 2.0, "cache_read": 0.025},
    "gpt-5-nano": {"input": 0.05, "output": 0.4, "cache_read": 0.005},
    "gpt-4.1": {"input": 2.5, "output": 10.0, "cache_read": 0.5},
    "gpt-4.1-mini": {"input": 0.4, "output": 1.6, "cache_read": 0.08},
    "gpt-4.1-nano": {"input": 0.1, "output": 0.4, "cache_read": 0.02},
    "gpt-4o": {"input": 2.5, "output": 10.0, "cache_read": 0.625},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6, "cache_read": 0.075},
    "o3": {"input": 2.0, "output": 8.0, "cache_read": 0.5},
    "o3-mini": {"input": 1.1, "output": 4.4, "cache_read": 0.275},
    "o4-mini": {"input": 1.1, "output": 4.4, "cache_read": 0.275},
    "codex-mini": {"input": 0.25, "output": 2.0, "cache_read": 0.025},
    # Anthropic
    "claude-opus-4-7": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75, "thinking": 75.0},
    "claude-opus-4-1": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75, "thinking": 75.0},
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75, "thinking": 15.0},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75, "thinking": 15.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0, "cache_read": 0.1, "cache_write": 1.25, "thinking": 5.0},
    "claude-haiku-3-5": {"input": 0.8, "output": 4.0, "cache_read": 0.08, "cache_write": 1.0, "thinking": 4.0},
}


def _lookup(model: str) -> ModelPricing:
    """Return the best pricing row for a model identifier (fuzzy match)."""
    if not model:
        return {}
    key = model.strip().lower()
    if key in _PRICING:
        return _PRICING[key]
    # Try matching by family prefix.
    for prefix, pricing in _PRICING.items():
        if key.startswith(prefix):
            return pricing
    # Date-suffixed variants like claude-sonnet-4-5-20250929 -> base claude-sonnet-4-5
    for prefix, pricing in _PRICING.items():
        if key.startswith(prefix + "-"):
            return pricing
    return {}


def calculate_cost(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    thinking_tokens: int = 0,
) -> float:
    p = _lookup(model)
    if not p:
        return 0.0
    thinking_rate = p.get("thinking", p.get("output", 0.0))
    return (
        input_tokens * p.get("input", 0.0)
        + output_tokens * p.get("output", 0.0)
        + cache_read_tokens * p.get("cache_read", 0.0)
        + cache_write_tokens * p.get("cache_write", p.get("input", 0.0))
        + thinking_tokens * thinking_rate
    ) / 1_000_000.0
