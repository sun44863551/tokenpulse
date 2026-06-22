"""Public parser registry."""

from __future__ import annotations

from .aider import AiderParser
from .base import BaseParser, ParseContext, ParseEvent
from .claude_code import ClaudeCodeParser
from .codex import CodexParser
from .continue_dev import ContinueDevParser
from .cursor import CursorWorkspaceParser


_REGISTRY: dict[str, BaseParser] = {
    "codex": CodexParser(),
    "claude-code": ClaudeCodeParser(),
    "aider": AiderParser(),
    "continue-dev": ContinueDevParser(),
    "cursor": CursorWorkspaceParser(),
}


def get_parser(tool: str) -> BaseParser | None:
    return _REGISTRY.get(tool)


def supported_tools() -> list[str]:
    return list(_REGISTRY.keys())


__all__ = [
    "AiderParser",
    "BaseParser",
    "ClaudeCodeParser",
    "CodexParser",
    "ContinueDevParser",
    "CursorWorkspaceParser",
    "ParseContext",
    "ParseEvent",
    "get_parser",
    "supported_tools",
]
