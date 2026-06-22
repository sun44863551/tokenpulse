"""\u9762\u5411 Continue.dev VS Code \u6269\u5c55\u7684 core.log \u5c3e\u90e8\u8ddf\u8e2a\u89e3\u6790\u5668\u3002

Continue.dev \u662f\u4e00\u4e2a\u5e38\u9a7b\u4e8e VS Code \u8fdb\u7a0b\u4e2d\u7684 AI \u7f16\u7a0b\u52a9\u624b\uff0c
\u5b83\u5e76\u4e0d\u63d0\u4f9b\u6807\u51c6\u5316\u7684\u8ba1\u8d39\u63a5\u53e3\u3002\u4f46\u5728\u7528\u6237\u4e3b\u76ee\u5f55\u4e0b\u4f1a\u8f93\u51fa\u4e00\u4e2a core.log\uff0c
\u8be5\u65e5\u5fd7\u5305\u542b\u6837\u5f0f\u7c7b\u4f3c\u4e8e\u4ee5\u4e0b\u5185\u5bb9\uff08\u4ec5\u4f5c\u793a\u4f8b\uff0c\u683c\u5f0f\u53ef\u80fd\u968f\u7248\u672c\u53d8\u5316\uff09\uff1a

  [2025-09-30T12:00:01.234Z] [LLMLogFormatter] prompt_tokens=125, completion_tokens=42, total_tokens=167
  [2025-09-30T12:00:01.235Z] [LLMLogFormatter] {\"prompt\":\"...\",\"completion\":\"...\",\"usage\":{\"total_tokens\":167,\"prompt_tokens\":125,\"completion_tokens\":42,\"cost\":0.0012}}

\u672c\u89e3\u6790\u5668\u5e94\u5bf9\u7684\u573a\u666f\u662f\uff1a
1. \u8c03\u7528\u8005\u5df2\u7ecf\u901a\u8fc7 watchdog / \u5b9a\u671f\u8bfb\u53d6 core.log\uff0c\u4e00\u6b21\u63a8\u9001 1 \u884c\uff08\u4e5f\u53ef\u4ee5\u662f\u591a\u884c\uff09\u3002
2. \u884c\u4e2d\u53ef\u80fd\u662f\u5e72\u51c0\u6587\u672c\uff0c\u4e5f\u53ef\u80fd\u4e2d\u9014\u88ab\u88c1\u65ad\u3002\u6211\u4eec\u4fdd\u7559\u672a\u5b8c\u6210\u7684
   JSON \u7247\u6bb5\uff0c\u4e0b\u4e00\u884c\u53ef\u80fd\u4f1a\u88ab feed() \u62fc\u63a5\u3002
3. \u4ec5\u5f53\u4e00\u4e2a\u5305\u542b usage \u5b57\u6bb5\u7684\u5b8c\u6574 JSON \u88ab\u8d4b\u503c\u540e\uff0c\u624d\u8f93\u51fa ParseEvent\u3002

\u63a5\u53e3\u9075\u5faa BaseParser\u3002\u4f7f\u7528\u65b9\u6cd5\u53c2\u8003 tokenpulse/parsers/__init__.py\u3002
"""

from __future__ import annotations

import json
import re
import time
from typing import Iterable, List, Optional

from ..core.models import UsageRecord
from .base import BaseParser, ParseContext, ParseEvent, make_record_id


# \u8bc6\u522b\u4e24\u79cd core.log \u6837\u5f0f:
#   1) \u7eaf\u6587\u672c\u884c\uff0c\u683c\u5f0f "prompt_tokens=125 completion_tokens=42 total_tokens=167"
#   2) \u4e2d\u9014\u643a\u5e26 JSON \u7684\u4e00\u884c\uff0c\u4f8b\u5982 "[LLMLogFormatter] {\"prompt\":...,\"usage\":{...}}"

# \u6b63\u5219 1\uff1a\u4ece key=value \u6837\u5f0f\u63d0\u53d6 tokens\u3002\u4ec5\u4f5c\u4e3a\u201c\u4e2d\u7f13\u4e8b\u4ef6\u201d\u4f7f\u7528\u3002
_RE_KV_TOKENS = re.compile(
    r"prompt[_ ]?tokens?\s*[=:]\s*(?P<p>[\d.,]+)\s*[,;\s]*"
    r"completion[_ ]?tokens?\s*[=:]\s*(?P<c>[\d.,]+)\s*[,;\s]*"
    r"(?:total[_ ]?tokens?\s*[=:]\s*(?P<t>[\d.,]+))?",
    re.IGNORECASE,
)

# \u6b63\u5219 2\uff1a\u67e5\u627e\u4ee5 { \u5f00\u59cb\u3001\u4ee5 } \u7ed3\u675f\u7684 JSON \u5b50\u4e32\u3002
# \u91c7\u7528 [\s\S]+? \u4ee5\u5141\u8bb8\u591a\u884c\u3002
def _extract_json_object(text: str) -> Optional[str]:
    """Locate the first balanced { ... } object in `text`.
    Handles nested objects and skips string contents (incl. escapes).
    Returns the slice, or None if no balanced object is found.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == chr(0x5c):  # backslash
            escape = True
            continue
        if c == chr(0x22):  # double quote
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == chr(0x7b):  # open brace
            depth += 1
        elif c == chr(0x7d):  # close brace
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    return None




def _safe_int(s: str) -> int:
    try:
        return int(float(str(s).replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _safe_float(s) -> float:
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


class ContinueDevParser(BaseParser):
    """\u9762\u5411 Continue.dev core.log \u7684\u89e3\u6790\u5668\u3002

    \u80fd\u529b\uff1a
    - \u5904\u7406\u88ab\u4e2d\u9014\u88c1\u65ad\u7684 JSON \u7247\u6bb5\uff08\u6bd4\u5982\u591a\u884c\u8f93\u51fa\u3001\u4e0d\u5b8c\u6574\u7684 key=value\uff09
    - \u5b89\u5168\u5730 json.loads\uff08\u4f7f\u7528 try/except\uff09\uff0c\u4e0d\u4f1a\u8df3\u51fa
    - \u9047\u5230\u65e0\u6cd5\u89e3\u6790\u7684\u884c\u5b8c\u5168\u5ffd\u7565\uff0c\u4e0d\u5f71\u54cd\u540e\u7eed\u5904\u7406
    """

    tool = "continue-dev"

    def __init__(self) -> None:
        super().__init__()
        # \u6bcf\u4e2a ParseContext \u5360\u4e00\u4e2a\u672a\u5b8c\u6210\u7684 JSON buffer\u3002
        # \u91c7\u7528 dict[source_file, str] \u4e0e\u4e0a\u4e0b\u6587\u9694\u79bb\u3002
        self._buf: dict[str, str] = {}
        # \u53bb\u91cd key
        self._seen_hashes: set[tuple[str, str]] = set()

    # ---------------------------------------------------- internal
    def _try_flush_buffer(self, ctx: ParseContext) -> Optional[ParseEvent]:
        """\u5c1d\u8bd5\u5c06\u7f13\u51b2\u533a\u4e2d\u7684\u5b57\u7b26\u4e32\u8d77\u4e00\u4e2a\u5b8c\u6574 JSON \u53bb\u89e3\u6790\u3002\u89e3\u6790\u6210\u529f\u5e76\u542b usage \u5219\u8fd4\u56de event\u3002\u5426\u5219\u8fd4\u56de None\u3002"""
        buf = self._buf.get(ctx.source_file, "")
        if not buf:
            return None
        # \u4f18\u5148\u5c1d\u8bd5\u5168\u5c40 json.loads\u3002\u5982\u679c\u4e0d\u6210\u529f\uff0c\u5c1d\u8bd5\u7528\u6b63\u5219\u63d0\u53d6\u7b2c\u4e00\u4e2a { ... } \u3002
        try:
            obj = json.loads(buf)
        except (ValueError, TypeError):
            snippet = _extract_json_object(buf)
            if snippet is None:
                return None
            try:
                obj = json.loads(snippet)
            except (ValueError, TypeError):
                # \u4ecd\u4e0d\u6210\u529f\u3002\u4fdd\u7559\u7f13\u51b2\u533a\uff0c\u7b49\u5f85\u4e0b\u4e00\u884c\u8865\u9f50
                return None
            # \u6210\u529f\u4e86\uff01\u6e05\u7a7a\u7f13\u51b2\u533a\u4e2d\u4f7f\u7528\u8fc7\u7684\u90e8\u5206
            consumed_end = buf.find(snippet) + len(snippet)
            self._buf[ctx.source_file] = buf[consumed_end:]
        else:
            self._buf[ctx.source_file] = ""

        if not isinstance(obj, dict):
            return None
        usage = obj.get("usage") or obj
        if not isinstance(usage, dict):
            return None
        prompt = _safe_int(usage.get("prompt_tokens", usage.get("input_tokens", 0)))
        completion = _safe_int(usage.get("completion_tokens", usage.get("output_tokens", 0)))
        total = _safe_int(usage.get("total_tokens", prompt + completion))
        cost = _safe_float(usage.get("cost", 0))
        model = (
            obj.get("model")
            or obj.get("modelName")
            or usage.get("model")
            or "continue-dev"
        )
        if prompt + completion + total == 0:
            return None
        ts = _parse_timestamp(obj.get("ts")) or _parse_timestamp(obj.get("timestamp"))
        if not ts:
            ts = int(time.time() * 1000)
        # \u53bb\u91cd
        hash_key = (ctx.source_file, str(prompt), str(completion), str(total), str(cost), str(ts))
        if hash_key in self._seen_hashes:
            return None
        self._seen_hashes.add(hash_key)
        if len(self._seen_hashes) > 30_000:
            self._seen_hashes.clear()
        record = UsageRecord(
            id=make_record_id(self.tool, ctx.source_file, len(buf)),
            ts=ts,
            tool=self.tool,
            model=str(model),
            input_tokens=prompt,
            output_tokens=completion,
            cost=cost,
            session_id=ctx.session_id or "continue-dev-default",
            source_file=ctx.source_file,
        )
        return ParseEvent(usage=record, model_hint=str(model))

    def feed(
        self, line: str, context: ParseContext, line_offset: int
    ) -> Iterable[ParseEvent]:
        if not line:
            return
        # 1) \u4f18\u5148\u8bd5\u8bd5\u4ece\u8fd9\u4e00\u884c\u91cc\u9762\u80fd\u4e0d\u80fd\u62fe\u51fa\u5b8c\u6574 JSON
        m_str = _extract_json_object(line)
        if m_str:
            self._buf[context.source_file] = (
                self._buf.get(context.source_file, "") + m_str
            )
            ev = self._try_flush_buffer(context)
            if ev is not None:
                yield ev
        # 2) \u4f7f\u7528 key=value \u4e0e\u73b0\u6709\u7f13\u51b2\u533a\u62fc\u63a5
        if _RE_KV_TOKENS.search(line):
            self._buf[context.source_file] = (
                self._buf.get(context.source_file, "") + line
            )
            ev = self._try_flush_buffer(context)
            if ev is not None:
                yield ev
        # 3) \u542c\u4e0d\u61c2\u7684\u884c\u76f4\u63a5\u4e22\u5f03\uff0c\u4e0d\u4f1a\u8ba9\u7f13\u51b2\u533a\u65e0\u9650\u589e\u957f
        # \u5982\u679c\u4f60\u9700\u8981\u4e25\u683c\u62fc\u63a5\uff0c\u53ef\u4ee5\u5728\u8fd9\u91cc\u6539\u4e3a self._buf[...] += line

    def finalize(self, context: ParseContext) -> Iterable[ParseEvent]:
        # \u6700\u540e\u4e00\u6b21\u5c1d\u8bd5\u6d17\u51fa\u7f13\u51b2\u533a
        ev = self._try_flush_buffer(context)
        if ev is not None:
            yield ev
        # \u4f8b\u5982\u6ca1\u6709\u6d6e\u73b0\uff0c\u4e0d\u4ea7\u751f\u4efb\u4f55 event
        return


def _parse_timestamp(value) -> Optional[int]:
    """\u5c1d\u8bd5\u5c06\u591a\u79cd\u65f6\u95f4\u4e32\u8f6c\u4e3a\u6beb\u79d2\u3002\u652f\u6301 ISO8601\u3001\u4e07\u5e74\u65e5\u671f\u3002"""
    if not value:
        return None
    if isinstance(value, (int, float)):
        # \u5c0f\u4e8e 1e12 \u8ba4\u4e3a\u662f\u79d2\uff0c\u5426\u5219\u6beb\u79d2
        return int(value) if value > 1e12 else int(value * 1000)
    if isinstance(value, str):
        # \u5c1d\u8bd5 ISO 8601
        from datetime import datetime
        s = value.strip()
        if not s:
            return None
        # \u5e38\u89c1\u683c\u5f0f: 2025-09-30T12:00:01.234Z
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(s, fmt)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue
    return None


# \u5feb\u901f\u6f14\u793a -------------------------------------------------------------------
if __name__ == "__main__":
    p = ContinueDevParser()
    ctx = p.new_context(r"C:\Users\test\.continue\logs\core.log")
    lines = [
        "[2025-09-30T12:00:01.234Z] [LLMLogFormatter] prompt_tokens=125, completion_tokens=42",
        "[2025-09-30T12:00:01.235Z] [LLMLogFormatter] {\"model\":\"gpt-4o-mini\",\"usage\":{\"prompt_tokens\":125,\"completion_tokens\":42,\"total_tokens\":167,\"cost\":0.0012}}",
        "[2025-09-30T12:00:02.123Z] [INFO] unrelated line",
    ]
    for i, line in enumerate(lines):
        for ev in p.feed(line, ctx, i):
            if ev.usage:
                u = ev.usage
                print(f"[{i}] {u.model}: {u.input_tokens} in / {u.output_tokens} out / ${u.cost:.4f} ts={u.ts}")
    # \u8d70\u4e2a finalize\uff0c\u4ee5\u9632\u6709\u672a\u51fa\u53d6\u7684\u7f13\u51b2
    for ev in p.finalize(ctx):
        if ev.usage:
            print("finalize:", ev.usage.model)
