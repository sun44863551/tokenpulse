"""Base classes shared by tool-specific log parsers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from ..core.models import UsageRecord, InteractionRecord


@dataclass
class ParseContext:
    """Per-file parser state."""

    tool: str
    source_file: str
    session_id: Optional[str] = None
    current_model: Optional[str] = None
    current_plan_type: Optional[str] = None
    # Once we have seen a `user` message in this file we know to count it
    # as an interaction.  Codex and Claude Code both emit a single user
    # message per turn, which is what subscription plans actually bill.
    seen_user_message: bool = False


def make_record_id(tool: str, source_file: str, line_offset: int) -> str:
    h = hashlib.sha1(f"{tool}|{source_file}|{line_offset}".encode("utf-8")).hexdigest()
    return h[:32]


def make_interaction_id(tool: str, session_id: str, ts: int, count: int) -> str:
    h = hashlib.sha1(f"{tool}|{session_id}|{ts}|{count}".encode("utf-8")).hexdigest()
    return h[:32]


class BaseParser:
    """Common helpers for stateful JSONL parsers."""

    tool: str = "unknown"

    def new_context(self, source_file: str) -> ParseContext:
        return ParseContext(tool=self.tool, source_file=source_file)

    # Subclasses override one of these.
    def feed(self, line: str, context: ParseContext, line_offset: int) -> Iterable[ParseEvent]:
        return ()

    def finalize(self, context: ParseContext) -> Iterable[ParseEvent]:
        return ()


@dataclass
class ParseEvent:
    """Result of parsing a single line or finalizing a file."""

    usage: Optional[UsageRecord] = None
    interaction: Optional[InteractionRecord] = None
    model_hint: Optional[str] = None
    plan_type_hint: Optional[str] = None


def safe_json(line: str) -> Optional[dict[str, Any]]:
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except (ValueError, TypeError):
        return None
