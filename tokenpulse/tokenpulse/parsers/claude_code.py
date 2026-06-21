"""Parser for Claude Code JSONL session logs.

Claude Code writes ``<hash>.jsonl`` files under
``~/.claude/projects/<project>/<hash>.jsonl``.  Each line is a JSON
object; the ones we care about are:

* ``{"type": "user", "message": {...}}`` -- one per user turn
* ``{"type": "assistant", "message": {"model": "...", "usage": {...},
   "content": [...]}}`` -- one per assistant response
* ``{"type": "system", "sessionId": "..."}`` -- session bootstrap
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from ..core.models import UsageRecord, InteractionRecord
from ..core.pricing import calculate_cost
from .base import BaseParser, ParseContext, ParseEvent, make_record_id, make_interaction_id, safe_json


class ClaudeCodeParser(BaseParser):
    tool = "claude-code"

    def feed(self, line: str, context: ParseContext, line_offset: int) -> Iterable[ParseEvent]:
        parsed = safe_json(line)
        if parsed is None:
            return ()

        ev_type = parsed.get("type")

        # ---- session bootstrap ------------------------------------------
        if ev_type == "system":
            sid = parsed.get("sessionId") or (parsed.get("payload") or {}).get("sessionId")
            if sid:
                context.session_id = sid
            return ()

        # ---- user turn ---------------------------------------------------
        if ev_type == "user":
            if context.seen_user_message:
                return ()
            ts_ms = self._coerce_ts(parsed.get("timestamp"), context)
            context.seen_user_message = True
            if not context.session_id:
                # Use the file path as a fallback session key.
                context.session_id = context.source_file
            return (
                ParseEvent(
                    interaction=InteractionRecord(
                        id=make_interaction_id(
                            self.tool, context.session_id, ts_ms, 0
                        ),
                        ts=ts_ms,
                        tool=self.tool,
                        session_id=context.session_id,
                        source_file=context.source_file,
                    )
                ),
            )

        # ---- assistant message ------------------------------------------
        if ev_type == "assistant":
            message = parsed.get("message") or {}
            usage = message.get("usage")
            if not usage:
                return ()
            model = message.get("model") or "unknown"
            if model == "<synthetic>":
                return ()
            ts_ms = self._coerce_ts(message.get("timestamp") or parsed.get("timestamp"), context)
            if not context.session_id:
                context.session_id = context.source_file
            input_tokens = int(usage.get("input_tokens") or 0)
            output_tokens = int(usage.get("output_tokens") or 0)
            cache_read = int(usage.get("cache_read_input_tokens") or 0)
            cache_write = int(usage.get("cache_creation_input_tokens") or 0)
            thinking = int(usage.get("thinking_tokens") or 0)
            record = UsageRecord(
                id=make_record_id(self.tool, context.source_file, line_offset),
                ts=ts_ms,
                tool=self.tool,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
                thinking_tokens=thinking,
                cost=calculate_cost(
                    model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_read_tokens=cache_read,
                    cache_write_tokens=cache_write,
                    thinking_tokens=thinking,
                ),
                session_id=context.session_id,
                source_file=context.source_file,
            )
            return (ParseEvent(usage=record, model_hint=model),)

        return ()

    @staticmethod
    def _coerce_ts(value: Any, context: ParseContext) -> int:
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(value if value > 1e12 else value * 1000)
        if isinstance(value, str):
            try:
                from datetime import datetime
                v = value.replace("Z", "+00:00")
                dt = datetime.fromisoformat(v)
                return int(dt.timestamp() * 1000)
            except ValueError:
                return 0
        return 0
