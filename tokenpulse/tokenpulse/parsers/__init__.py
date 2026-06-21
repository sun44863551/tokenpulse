"""Public parser registry."""

from __future__ import annotations

from .base import BaseParser, ParseContext, ParseEvent
from .codex import CodexParser
from .claude_code import ClaudeCodeParser


_REGISTRY: dict[str, BaseParser] = {
    "codex": CodexParser(),
    "claude-code": ClaudeCodeParser(),
}


def get_parser(tool: str) -> BaseParser | None:
    return _REGISTRY.get(tool)


def supported_tools() -> list[str]:
    return list(_REGISTRY.keys())


__all__ = [
    "BaseParser",
    "ParseContext",
    "ParseEvent",
    "get_parser",
    "supported_tools",
]
