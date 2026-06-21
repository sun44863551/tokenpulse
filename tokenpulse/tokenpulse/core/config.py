"""Configuration: where to find logs, where to store data, what to watch."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _home() -> Path:
    """Best-effort cross-platform home directory."""
    return Path(os.path.expanduser("~"))


@dataclass(frozen=True)
class SourceConfig:
    """How to locate logs for one tool."""

    tool: str
    label: str
    paths: tuple[Path, ...]
    # When the path is a directory we recursively pick *.jsonl.
    # When the path is a file we tail it directly.
    env_override: tuple[str, ...] = field(default_factory=tuple)


def discover_sources() -> list[SourceConfig]:
    """Find logs for every supported tool on this machine."""

    home = _home()
    env = os.environ

    sources: list[SourceConfig] = []

    # ---- Codex -----------------------------------------------------------
    codex_root = Path(env.get("CODEX_HOME", "") or (home / ".codex"))
    codex_sessions = codex_root / "sessions"
    codex_archived = codex_root / "archived_sessions"
    if codex_sessions.exists() or codex_archived.exists():
        sources.append(
            SourceConfig(
                tool="codex",
                label="Codex",
                paths=(codex_sessions, codex_archived),
                env_override=("CODEX_HOME", "AIUSAGE_CODEX_PATH"),
            )
        )

    # ---- Claude Code -----------------------------------------------------
    claude_dir = Path(env.get("CLAUDE_CONFIG_DIR", "") or (home / ".claude"))
    claude_projects = claude_dir / "projects"
    if claude_projects.exists():
        sources.append(
            SourceConfig(
                tool="claude-code",
                label="Claude Code",
                paths=(claude_projects,),
                env_override=("CLAUDE_CONFIG_DIR", "AIUSAGE_CLAUDE_CODE_PATH"),
            )
        )

    return sources


def data_dir() -> Path:
    """Where TokenPulse stores its database and settings."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(_home() / "AppData" / "Local")))
    elif "darwin" in os.sys.platform:
        base = _home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(_home() / ".local" / "share")))
    target = base / "TokenPulse"
    target.mkdir(parents=True, exist_ok=True)
    return target


def db_path() -> Path:
    return data_dir() / "tokenpulse.db"


def settings_path() -> Path:
    return data_dir() / "settings.json"


# Plan tier classification - used to decide whether the user is on a
# "tokens" plan (charged by token volume) or a "token plan" (charged per
# interaction / turn).  Heuristics:
#   * codex `plan_type` of `plus` / `pro` / `team` / `enterprise` -> interactions
#   * claude code Max / Pro plan -> interactions
#   * everything else (API key with no subscription) -> tokens
INTERACTION_PLANS = {
    "plus",
    "pro",
    "team",
    "enterprise",
    "free",
    "max",
}


def looks_like_interaction_plan(plan_type: str | None) -> bool:
    if not plan_type:
        return False
    return plan_type.strip().lower() in INTERACTION_PLANS
