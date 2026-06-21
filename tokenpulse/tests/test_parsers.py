"""Smoke tests for the parsers.  Run with: ``python -m tests.test_parsers``."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Allow running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tokenpulse.parsers import get_parser  # noqa: E402
from tokenpulse.parsers.base import ParseContext  # noqa: E402
from tokenpulse.storage.db import Storage  # noqa: E402


# A minimal Codex-style session log.
CODEX_SAMPLE = [
    {"type": "session_meta", "payload": {"id": "abc123", "timestamp": "2026-01-01T00:00:00Z"}},
    {"type": "turn_context", "payload": {"model": "gpt-5"}},
    {"type": "event_msg", "payload": {"type": "task_started"}},
    {
        "type": "event_msg",
        "payload": {
            "type": "user_message",
            "message": "Hello, world",
        },
    },
    {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "last_token_usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 50,
                    "output_tokens": 30,
                    "reasoning_output_tokens": 5,
                },
            },
            "rate_limits": {
                "primary": {"used_percent": 10.0, "window_minutes": 300, "resets_at": 1700000000},
                "secondary": {"used_percent": 25.0, "window_minutes": 10080, "resets_at": 1701000000},
                "plan_type": "plus",
            },
        },
    },
]


# A minimal Claude Code session log.
CLAUDE_SAMPLE = [
    {"type": "system", "sessionId": "xyz789"},
    {"type": "user", "message": {"content": [{"type": "text", "text": "hi"}]}},
    {
        "type": "assistant",
        "message": {
            "model": "claude-sonnet-4-5",
            "id": "msg_1",
            "usage": {
                "input_tokens": 200,
                "output_tokens": 80,
                "cache_read_input_tokens": 100,
                "cache_creation_input_tokens": 10,
                "thinking_tokens": 5,
            },
            "content": [{"type": "tool_use", "name": "Bash", "input": {}}],
        },
    },
]


def test_codex_parser() -> None:
    p = get_parser("codex")
    ctx = p.new_context("/tmp/fake.jsonl")
    usage = interaction = None
    for i, line in enumerate(CODEX_SAMPLE, start=1):
        for ev in p.feed(json.dumps(line), ctx, i):
            if ev.usage is not None:
                usage = ev.usage
            if ev.interaction is not None:
                interaction = ev.interaction
    assert usage is not None, "expected a usage record"
    assert usage.tool == "codex"
    assert usage.model == "gpt-5"
    assert usage.input_tokens == 100
    assert usage.output_tokens == 30
    assert usage.cache_read_tokens == 50
    assert usage.thinking_tokens == 5
    assert usage.plan_type == "plus"
    assert usage.primary_used_percent == 10.0
    assert interaction is not None
    assert interaction.session_id == "abc123"
    assert interaction.tool == "codex"
    print("  codex parser: OK (tokens=%d, plan=%s)" % (usage.total_tokens, usage.plan_type))


def test_claude_code_parser() -> None:
    p = get_parser("claude-code")
    ctx = p.new_context("/tmp/fake.jsonl")
    usage = interaction = None
    for i, line in enumerate(CLAUDE_SAMPLE, start=1):
        for ev in p.feed(json.dumps(line), ctx, i):
            if ev.usage is not None:
                usage = ev.usage
            if ev.interaction is not None:
                interaction = ev.interaction
    assert usage is not None
    assert usage.tool == "claude-code"
    assert usage.model == "claude-sonnet-4-5"
    assert usage.input_tokens == 200
    assert usage.output_tokens == 80
    assert usage.cache_read_tokens == 100
    assert usage.cache_write_tokens == 10
    assert usage.thinking_tokens == 5
    assert interaction is not None
    assert interaction.session_id == "xyz789"
    print("  claude-code parser: OK (tokens=%d)" % usage.total_tokens)


def test_storage_roundtrip() -> None:
    from tokenpulse.core.models import UsageRecord
    db = Storage(Path(tempfile.gettempdir()) / "tokenpulse_unit_test.db")
    rec = UsageRecord(
        id="unit-1",
        ts=1700000000000,
        tool="codex",
        model="gpt-5",
        input_tokens=10,
        output_tokens=5,
        cache_read_tokens=0,
        cache_write_tokens=0,
        thinking_tokens=0,
        cost=0.0001,
        session_id="s",
        source_file="/tmp/x.jsonl",
        plan_type="plus",
        primary_used_percent=42.0,
    )
    db.upsert_usage(rec)
    t = db.totals()
    assert t.records == 1
    assert t.input_tokens == 10
    assert t.output_tokens == 5
    rl = db.latest_rate_limit()
    assert rl is not None
    assert rl.plan_type == "plus"
    assert rl.primary_used_percent == 42.0
    # Second insert with same id should NOT increment records.
    rec2 = UsageRecord(
        id="unit-1",
        ts=1700000000000,
        tool="codex",
        model="gpt-5",
        input_tokens=20,
        output_tokens=10,
        cache_read_tokens=0,
        cache_write_tokens=0,
        thinking_tokens=0,
        cost=0.0002,
        session_id="s",
        source_file="/tmp/x.jsonl",
    )
    db.upsert_usage(rec2)
    t = db.totals()
    assert t.records == 1, "REPLACE should not increment records counter"
    assert t.input_tokens == 20
    print("  storage roundtrip: OK (records=%d, in=%d, cost=%.4f)" % (t.records, t.input_tokens, t.cost))
    db.close()


def main() -> int:
    print("running parser tests...")
    test_codex_parser()
    test_claude_code_parser()
    test_storage_roundtrip()
    print("all tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())