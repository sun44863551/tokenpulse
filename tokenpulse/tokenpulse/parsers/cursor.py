"""\u9762\u5411 Cursor IDE \u672c\u5730\u5b58\u50a8\u7684\u9879\u76ee\u7ea7\u89e3\u6790\u5668\u3002

Cursor \u4f1a\u5728\u4e0b\u5217\u4f4d\u7f6e\u521b\u5efa\u672c\u5730\u5b58\u50a8\uff08Windows\uff09\uff1a

  %APPDATA%\\Cursor\\User\\workspaceStorage\\<hash>\\
  \u251c\u2500\u2500 workspace.json                          \u2713 \u4fdd\u5b58\u9879\u76ee\u8def\u5f84
  \u251c\u2500\u2500 state.vscdb                            \u2713 \u5168\u5c40\u72b6\u6001 SQLite
  \u251c\u2500\u2500 state.session.sqlite                  \u2713 \u4f1a\u8bdd\u72b6\u6001
  \u2514\u2500\u2500 \u4f1a\u8bdd\u76ee\u5f55\\*.sqlite            \u2713 \u4f1a\u8bdd\u5b9e\u4f53

\u672c\u89e3\u6790\u5668\u4e0d\u5b9c\u5168\u90e8\u8bfb\u53d6\u8fd9\u4e9b\u6587\u4ef6\uff08\u4f1a\u5f88\u6162\u4e14\u9700\u8981\u5b8c\u6574 schema\uff09\uff0c
\u800c\u662f\u63d0\u4f9b\u4e00\u5957\u53ef\u63d2\u62d4\u7684\u5b9e\u7528\u51fd\u6570\uff1a

  - iter_workspaces(root)\uff1a\u904d\u5386 workspaceStorage \u4e0b\u7684\u6240\u6709\u54c8\u5e0c\u5b50\u76ee\u5f55\uff0c\u63d0\u4f9b
    workspace.json \u4e2d\u7684\u9879\u76ee\u8def\u5f84\u3002
  - scan_session_databases(workspace_dir)\uff1a\u67e5\u627e\u53ef\u80fd\u5b58\u653e\u4f1a\u8bdd\u4f7f\u7528\u91cf\u7684 SQLite \u6587\u4ef6\uff0c
    \u8c03\u7528\u8005\u53ef\u9009\u62e9\u67e5\u8be2\u54ea\u4e9b\u8868\u3002
  - extract_token_usage_from_cursor_vscdb(path, queries)\uff1a\u8fd0\u884c\u591a\u4e2a\u9884\u8bbe\u67e5\u8be2\uff0c\u8fd4\u56de\u4f30\u8ba1\u7684
    token \u4f7f\u7528\u91cf\u3002\u8fd9\u91cc\u67e5\u8be2\u4ec5\u4f5c\u4e3a\u793a\u4f8b\uff0c\u5b9e\u9645\u67e5\u8be2\u4f9d\u8d56 Cursor \u7248\u672c\u3002
  - BaseParser.feed()\uff1a\u8c03\u7528\u8005\u53ef\u4ee5\u9009\u62e9\u4ed8\u4e88\u6bcf\u4e2a workspaceStorage \u5b50\u76ee\u5f55\u4f5c\u4e3a\u4e00\u4e2a
    \u201csource_file\u201d\uff0c\u8c03\u7528\u8005\u63a8\u9001\u6bcf\u4e2a .sqlite \u6587\u4ef6\u7684\u53d8\u5316\u884c\u8fdb\u6765\u3002\u6211\u4eec\u8fd9\u91cc
    \u4ec5\u4f5c\u6a21\u677f\u3002

\u5728\u8be5\u6587\u4ef6\u4e2d\uff0c\u67e5\u8be2\u90e8\u5206\u662f\u9c81\u68d2\u7684\u67b6\u6784\u793a\u4f8b\uff08Cursor \u672a\u516c\u5f00\u5b8c\u6574 schema\uff09\uff0c
\u4f60\u53ef\u4ee5\u6839\u636e\u81ea\u5df1 Cursor \u7248\u672c\u7684\u5b9e\u9645\u8868\u7ed3\u6784\u8c03\u6574\u67e5\u8be2\u3002
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Tuple

from ..core.models import UsageRecord
from .base import BaseParser, ParseContext, ParseEvent, make_record_id


# ------------------------------------------------------------------ \u5e38\u91cf
# Cursor \u5728 Windows \u4e0a\u7684\u9ed8\u8ba4\u6839\u76ee\u5f55\u3002\u4f60\u53ef\u4ee5\u901a\u8fc7 CURSOR_USER_DATA_DIR \u8986\u76d6\u3002
DEFAULT_WINDOWS_ROOT = Path(os.environ.get("APPDATA", str(Path.home()))) / "Cursor" / "User" / "workspaceStorage"


# \u793a\u4f8b\u67e5\u8be2\u3002\u53d6\u503c\u65b9\u5f0f\u4e3a (table_name, sql) \u3002
# \u4e0d\u540c\u7248\u672c\u7684 Cursor \u53ef\u80fd\u4f1a\u4f7f\u7528\u4e0d\u540c\u7684\u8868\u540d\uff0c\u8fd9\u91cc\u4ec5\u4f5c\u4e3a\u9ed8\u8ba4\u3002
# \u4f60\u53ef\u4ee5\u5728\u8c03\u7528\u65f6\u4f20\u5165\u81ea\u5df1\u7684\u67e5\u8be2\u3002
DEFAULT_QUERIES: List[Tuple[str, str]] = [
    # \u5c1d\u8bd5\u8bfb ItemTable \u4e2d\u7684 usage / tokens \u5b57\u6bb5
    (
        "ItemTable",
        "SELECT key, value FROM ItemTable "
        "WHERE key LIKE '%token%' OR key LIKE '%usage%' OR key LIKE '%model%'",
    ),
    # \u5c1d\u8bd5\u4ece cursorDiskKV \u8868\u8bfb\u53d6\u4f1a\u8bdd\u4f7f\u7528\u91cf
    (
        "cursorDiskKV",
        "SELECT key, value FROM cursorDiskKV "
        "WHERE key LIKE 'composerData:%token%' OR key LIKE 'composerData:%usage%'",
    ),
]


# ------------------------------------------------------------------ \u5de5\u5177\u51fd\u6570
def iter_workspaces(root: Optional[Path] = None) -> Iterator[Tuple[str, Path, Optional[Path]]]:
    """\u904d\u5386 Cursor workspaceStorage \u4e0b\u7684\u6240\u6709\u9879\u76ee\u3002

    \u8fd4\u56de\uff1a(\u54c8\u5e0c\u540d, \u5b50\u76ee\u5f55, workspace.json \u4e2d\u7684 folder \u5b57\u6bb5\uff09
    """
    base = Path(root) if root else DEFAULT_WINDOWS_ROOT
    if not base.exists():
        return
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        ws_file = child / "workspace.json"
        folder: Optional[Path] = None
        if ws_file.is_file():
            try:
                with ws_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                # \u5b98\u65b9\u683c\u5f0f: {"folder": "file:///c%3A/foo/bar"} \u6216\u76f4\u63a5 {"folder": "/c/foo/bar"}
                raw_folder = data.get("folder") or data.get("workspace") or ""
                if raw_folder.startswith("file:///"):
                    # Windows: file:///C:/foo/bar \u2192 C:/foo/bar
                    raw_folder = raw_folder[len("file:///"):]
                elif raw_folder.startswith("file://"):
                    raw_folder = raw_folder[len("file://"):]
                # \u5904\u7406 URL-encoded \u5b57\u7b26
                from urllib.parse import unquote
                folder = Path(unquote(raw_folder)) if raw_folder else None
            except (OSError, ValueError):
                pass
        yield child.name, child, folder


def scan_session_databases(workspace_dir: Path) -> List[Path]:
    """\u67e5\u627e workspace \u4e0b\u53ef\u80fd\u5b58\u653e\u4f1a\u8bdd\u4f7f\u7528\u91cf\u7684 SQLite \u6587\u4ef6\u3002

    \u5305\u62ec\uff1a
    - state.vscdb            \uff08\u5168\u5c40\u72b6\u6001\uff0c\u5305\u542b composerData\uff09
    - state.session.sqlite    \uff08\u4f1a\u8bdd\u72b6\u6001\uff09
    - \u4efb\u4f55 *.sqlite      \uff08\u5b9e\u9a8c\u6027\uff0c\u53ef\u80fd\u662f\u9644\u52a0\u63d2\u4ef6\u4ea7\u751f\uff09
    """
    if not workspace_dir.is_dir():
        return []
    seen: set = set()
    results: List[Path] = []
    for pattern in ("state.vscdb", "state.session.sqlite"):
        cand = workspace_dir / pattern
        if cand.is_file() and cand not in seen:
            seen.add(cand)
            results.append(cand)
    for db in workspace_dir.glob("*.sqlite"):
        if db not in seen:
            seen.add(db)
            results.append(db)
    return results


def _try_query_value(cursor: sqlite3.Cursor, key: str) -> Optional[dict]:
    """\u5c1d\u8bd5\u67e5\u8be2\u4e00\u4e2a key\uff0c\u8fd4\u56de\u53ef\u80fd\u662f dict/list/int/float \u4e2d\u7684\u4e00\u4e2a\u3002"""
    try:
        cursor.execute(
            "SELECT value FROM ItemTable WHERE key = ? LIMIT 1", (key,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        raw = row[0]
        if isinstance(raw, (bytes, bytearray)):
            try:
                return json.loads(raw.decode("utf-8", errors="replace"))
            except ValueError:
                return None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except ValueError:
                return {"raw": raw}
        return {"raw": raw}
    except sqlite3.OperationalError:
        return None


def extract_token_usage_from_cursor_vscdb(
    db_path: Path,
    queries: Optional[List[Tuple[str, str]]] = None,
) -> Optional[dict]:
    """\u4ece\u4e00\u4e2a Cursor vscdb \u6587\u4ef6\u91cc\u63cf\u51fa\u4f30\u8ba1\u7684 token \u4f7f\u7528\u91cf\u3002

    \u8fd4\u56de\u7684 dict \u5305\u542b\uff1a
      tokens_input, tokens_output, cost\uff08\u5982\u679c\u80fd\u63a8\u65ad\uff09\u3001model\u3001
      cursor_workspace_hash, source_file\u3002
    \u4efb\u4e00\u4e2a\u5b57\u6bb5\u90fd\u53ef\u80fd\u4e3a None\u3002\u5982\u679c\u5168\u4e3a None\uff0c\u8fd4\u56de None\u3002

    \u6ce8\u610f\uff1aCursor \u7684 schema \u968f\u7248\u672c\u53d8\u5316\u3002\u8fd9\u91cc\u7684\u67e5\u8be2\u4ec5\u4f5c\u4e3a\u793a\u4f8b\u67b6\u6784\u3002
    \u4f60\u53ef\u4ee5\u6839\u636e\u5b9e\u9645 cursorDiskKV \u8868\u7684 key \u524d\u7f00\u4e0e\u5b57\u6bb5\u8c03\u6574\u3002
    """
    if not db_path.is_file():
        return None
    queries = queries or DEFAULT_QUERIES
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        cursor = con.cursor()
    except sqlite3.OperationalError as exc:
        print(f"[cursor] cannot open {db_path}: {exc}", flush=True)
        return None
    try:
        result: dict = {
            "tokens_input": None,
            "tokens_output": None,
            "cost": None,
            "model": None,
            "ts": None,
        }
        any_hit = False
        for table, sql in queries:
            try:
                cursor.execute(sql)
            except sqlite3.OperationalError:
                # \u8868\u4e0d\u5b58\u5728\uff0c\u8df3\u8fc7
                continue
            for row in cursor.fetchall():
                key = row["key"] if "key" in row.keys() else None
                value = row["value"] if "value" in row.keys() else None
                if not key:
                    continue
                kl = key.lower()
                # \u53ea\u5904\u7406\u542b token / usage / model \u7684\u952e
                if any_hit and "model" not in kl:
                    continue
                # \u5982\u679c value \u662f\u4e32\uff0c\u5c1d\u8bd5\u53cd\u5e8f\u5217\u5316
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except ValueError:
                        value = {"raw": value}
                elif isinstance(value, (bytes, bytearray)):
                    try:
                        value = json.loads(value.decode("utf-8", errors="replace"))
                    except ValueError:
                        value = None
                if not isinstance(value, dict):
                    continue
                # \u63a8\u65ad model
                if "model" in kl and isinstance(value.get("modelName"), str):
                    result["model"] = value["modelName"]
                # \u63a8\u65ad tokens
                for k_in, k_out in (
                    ("tokens", "tokens"),
                    ("usage", "usage"),
                    ("inputTokens", "tokens_input"),
                    ("outputTokens", "tokens_output"),
                ):
                    if k_in in kl:
                        if isinstance(value.get("inputTokens"), (int, float)):
                            result["tokens_input"] = int(value["inputTokens"])
                        if isinstance(value.get("outputTokens"), (int, float)):
                            result["tokens_output"] = int(value["outputTokens"])
                        if isinstance(value.get("totalTokens"), (int, float)):
                            # \u5982\u679c\u4e24\u4e2a\u90fd\u6ca1\u6709\uff0c\u5c1d\u8bd5\u4ece total \u62c6\u5206
                            if result["tokens_input"] is None and result["tokens_output"] is None:
                                total = int(value["totalTokens"])
                                result["tokens_input"] = total // 2
                                result["tokens_output"] = total - result["tokens_input"]
                # cost
                if "cost" in kl and isinstance(value.get("cost"), (int, float)):
                    result["cost"] = float(value["cost"])
                if "model" in kl and isinstance(value.get("model"), str):
                    result["model"] = value["model"]
                any_hit = True
        if not any_hit:
            return None
        result["source_file"] = str(db_path)
        return result
    finally:
        try:
            con.close()
        except Exception:
            pass


# ------------------------------------------------------------------ Parser
class CursorWorkspaceParser(BaseParser):
    """Cursor workspaceStorage \u4f4d\u7f6e\u7684\u9879\u76ee\u7ea7\u89e3\u6790\u5668\u3002

    \u8fd4\u56de\u4e2d\u7684 UsageRecord \u4ec5\u5305\u542b\u8be5 workspace \u5b9e\u65f6\u7684\u4f7f\u7528\u91cf\u589e\u91cf\uff08\u5982\u679c\u53ef\u63a8\u65ad\uff09\u3002
    """

    tool = "cursor"

    def __init__(self) -> None:
        super().__init__()
        # \u8bb0\u5f55\u4e0a\u4e00\u6b21\u770b\u5230\u7684 tokens\uff0c\u8ba1\u7b97\u589e\u91cf
        self._last_seen: dict[str, dict] = {}

    def feed(
        self, line: str, context: ParseContext, line_offset: int
    ) -> Iterable[ParseEvent]:
        """\u8c03\u7528\u8005\u9700\u63a8\u9001\u4e00\u4e2a SQLite \u6587\u4ef6\u7684\u8def\u5f84\u4f5c\u4e3a line\u3002

        \u8fd9\u91cc\u91c7\u7528\u201c\u4e00\u884c\u5c31\u662f\u4e00\u4e2a\u6587\u4ef6\u8def\u5f84\u201d\u7684\u7b80\u5316\u534f\u8bae\u3002\u5982\u679c\u4f60\u8981\u63a8\u9001
        \u589e\u91cf\u4e8b\u4ef6\uff0c\u8bf7\u5728\u8c03\u7528\u8005\u4fa7\u8bbe\u8ba1\u4e00\u4e2a\u7c7b\u4f3c cursorDiskKV \u7684 diff \u961f\u5217\u3002
        """
        path = Path(line.strip())
        if not path.is_file():
            return
        data = extract_token_usage_from_cursor_vscdb(path)
        if not data:
            return
        # \u8ba1\u7b97\u4e0e\u4e0a\u4e00\u6b21\u7684\u5dee\u503c
        last = self._last_seen.get(str(path))
        import time as _time
        ts = int(_time.time() * 1000)
        if last is None:
            # \u9996\u6b21\u770b\u5230\uff0c\u8bb0\u4e0b\u73b0\u72b6\uff0c\u4e0d\u8f93\u51fa\u4e8b\u4ef6
            self._last_seen[str(path)] = data
            return
        # \u8ba1\u7b97\u589e\u91cf
        di = (data.get("tokens_input") or 0) - (last.get("tokens_input") or 0)
        do = (data.get("tokens_output") or 0) - (last.get("tokens_output") or 0)
        dc = (data.get("cost") or 0.0) - (last.get("cost") or 0.0)
        if di <= 0 and do <= 0 and dc <= 0:
            # \u4ec0\u4e48\u90fd\u6ca1\u53d8\u5316\uff0c\u8df3\u8fc7
            return
        self._last_seen[str(path)] = data
        record = UsageRecord(
            id=make_record_id(self.tool, context.source_file, line_offset),
            ts=ts,
            tool=self.tool,
            model=str(data.get("model") or "cursor"),
            input_tokens=max(di, 0),
            output_tokens=max(do, 0),
            cost=max(dc, 0.0),
            session_id=context.session_id or "cursor-default",
            source_file=str(path),
        )
        yield ParseEvent(usage=record, model_hint=record.model)

    def finalize(self, context: ParseContext) -> Iterable[ParseEvent]:
        return ()


# \u5feb\u901f\u6f14\u793a -------------------------------------------------------------------
if __name__ == "__main__":
    # \u67e5\u770b\u672c\u673a\u662f\u5426\u88c5\u6709 Cursor\uff0c\u4ec5\u8f93\u51fa\u53d1\u73b0\u7684 workspace \u4fe1\u606f\u3002
    print("Scanning:", DEFAULT_WINDOWS_ROOT)
    found = 0
    for hash_name, ws_dir, folder in iter_workspaces():
        dbs = scan_session_databases(ws_dir)
        print(f"  [{hash_name[:8]}] folder={folder!s:.80s}  dbs={[d.name for d in dbs]}")
        found += 1
        if found > 10:
            print("  ... (truncated)")
            break
    if not found:
        print("  (no Cursor workspaces found on this machine)")
