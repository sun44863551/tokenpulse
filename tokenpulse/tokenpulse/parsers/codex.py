"""Parser for Codex CLI/Desktop JSONL session logs.

Codex writes one JSON object per line to ``~/.codex/sessions/`` and
``~/.codex/archived_sessions/``.  Relevant shapes:

* ``{"type": "session_meta", "payload": {"id": "..."}}`` -- session id
* ``{"type": "turn_context", "payload": {"model": "..."}}`` -- current model
* ``{"type": "event_msg", "payload": {"type": "token_count",
   "info": {"last_token_usage": {...}, "model_context_window": ...},
   "rate_limits": {"primary": {...}, "secondary": {...}, "plan_type": ...}}}``
* ``{"type": "event_msg", "payload": {"type": "user_message", ...}}`` --
   one per user turn (used to count interactions for subscription plans)
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from ..core.models import UsageRecord, InteractionRecord
from ..core.pricing import calculate_cost
from .base import BaseParser, ParseContext, ParseEvent, make_record_id, make_interaction_id, safe_json


class CodexParser(BaseParser):
    tool = "codex"

    def feed(self, line: str, context: ParseContext, line_offset: int) -> Iterable[ParseEvent]:
        parsed = safe_json(line)
        if parsed is None:
            return ()

        # --- session meta --------------------------------------------------
        if parsed.get("type") == "session_meta":
            payload = parsed.get("payload") or {}
            sid = payload.get("id")
            if sid:
                context.session_id = sid
            return ()

        # --- turn context (model hint) -------------------------------------
        if parsed.get("type") == "turn_context":
            payload = parsed.get("payload") or {}
            model = payload.get("model")
            if model:
                context.current_model = model
            return ()

        # --- event_msg wrappers -------------------------------------------
        if parsed.get("type") != "event_msg":
            return ()
        payload = parsed.get("payload") or {}
        ev_type = payload.get("type")

        # User message -> interaction.
        if ev_type == "user_message":
            ts_ms = self._coerce_ts(parsed.get("timestamp"), context)
            if not context.seen_user_message and context.session_id:
                # Count the first user_message per session as a turn.
                context.seen_user_message = True
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
                            plan_type=context.current_plan_type,
                        )
                    ),
                )
            return ()

        if ev_type != "token_count":
            return ()

        # --- token_count event --------------------------------------------
        info = payload.get("info") or {}
        usage = info.get("last_token_usage") or info.get("total_token_usage")
        if not usage:
            return ()

        model = (
            payload.get("model")
            or context.current_model
            or (parsed.get("payload") or {}).get("model")
            or "unknown"
        )
        ts_ms = self._coerce_ts(parsed.get("timestamp"), context)
        record = UsageRecord(
            id=make_record_id(self.tool, context.source_file, line_offset),
            ts=ts_ms,
            tool=self.tool,
            model=model,
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            cache_read_tokens=int(usage.get("cached_input_tokens") or 0),
            cache_write_tokens=0,  # Codex does not emit this.
            thinking_tokens=int(usage.get("reasoning_output_tokens") or 0),
            cost=calculate_cost(
                model,
                input_tokens=int(usage.get("input_tokens") or 0),
                output_tokens=int(usage.get("output_tokens") or 0),
                cache_read_tokens=int(usage.get("cached_input_tokens") or 0),
                thinking_tokens=int(usage.get("reasoning_output_tokens") or 0),
            ),
            session_id=context.session_id,
            source_file=context.source_file,
        )

        rate = payload.get("rate_limits") or {}
        primary = rate.get("primary") or {}
        secondary = rate.get("secondary") or {}
        credits = rate.get("credits") or {}
        # --- new Codex rate_limit fields (Codex CLI >= 0.20) --------
        # When the active model is provided by a third party (e.g.
        # MiniMax-M3) the entire block can be null.  We still persist
        # everything Codex sends so the UI can show an accurate
        # "no data" state and respect rate_limit_reached_type.
        record.plan_type = rate.get("plan_type")
        record.limit_id = rate.get("limit_id")
        record.limit_name = rate.get("limit_name")
        record.primary_used_percent = primary.get("used_percent")
        record.primary_resets_at = self._coerce_ts(primary.get("resets_at"), context)
        record.secondary_used_percent = secondary.get("used_percent")
        record.secondary_resets_at = self._coerce_ts(secondary.get("resets_at"), context)
        record.credits_has_credits = credits.get("has_credits")
        record.credits_unlimited = credits.get("unlimited")
        record.credits_balance = (
            str(credits.get("balance")) if credits.get("balance") is not None else None
        )
        record.individual_limit = rate.get("individual_limit")
        record.rate_limit_reached_type = rate.get("rate_limit_reached_type")
        if record.plan_type:
            context.current_plan_type = record.plan_type

        return (ParseEvent(usage=record, plan_type_hint=record.plan_type),)

    @staticmethod
    def _coerce_ts(value: Any, context: ParseContext) -> int:
        if value is None:
            return int(context.source_file and 0) or 0
        if isinstance(value, (int, float)):
            # Heuristic: if value looks like seconds, convert.
            if value < 1e12:
                return int(value * 1000)
            return int(value)
        if isinstance(value, str):
            try:
                from datetime import datetime
                # Accept Z-suffixed ISO strings.
                v = value.replace("Z", "+00:00")
                dt = datetime.fromisoformat(v)
                return int(dt.timestamp() * 1000)
            except ValueError:
                return 0
        return 0
