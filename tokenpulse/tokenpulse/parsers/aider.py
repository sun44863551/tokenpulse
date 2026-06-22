"""\u9762\u5411 Aider \u7684 markdown \u4f1a\u8bdd\u5386\u53f2\u6587\u4ef6\u89e3\u6790\u5668\u3002

Aider \u5728\u5de5\u4f5c\u76ee\u5f55\u4e2d\u4f1a\u4ea7\u751f\u540d\u4e3a .aider.chat.history.md \u7684\u6587\u4ef6\uff0c
\u8be5\u6587\u4ef6\u968f\u4f1a\u8bdd\u9010\u884c\u8ffd\u52a0\u3002\u6bcf\u4e2a commit \u4e0a\u65b9\u4f1a\u51fa\u73b0\u4e00\u4e2a\u201c\u4f7f\u7528\u91cf\u6458\u8981\u201d\u7247\u6bb5\uff0c
\u6837\u4f8b\uff08\u82f1\u6587\u4e0e\u4e2d\u6587\u4ea4\u9519\uff09\uff1a

  Tokens: 8.5k sent, 1.2k received. Cost: $0.12 message, $1.85 session.
  \u4ee3\u7406: 8.5k sent, 1.2k received\u3002\u4f1a\u8bdd\u6210\u672c: $0.12 (\u672c\u6761), $1.85 (\u4f1a\u8bdd\u7d2f\u8ba1)\u3002

\u672c\u89e3\u6790\u5668\u4e0d\u4f9d\u8d56\u89c2\u5bdf\u8005\u8bfb\u53d6\u5b8c\u6574\u6587\u4ef6\uff0c\u800c\u662f\u4ee5**\u8c03\u7528\u8005\u63a8\u9001\u4e86\u4ec0\u4e48\u6587\u672c** \u4e3a\u51c6\u3002
\u4f8b\u5982\uff1aAider \u7684 file_watcher \u53d1\u73b0 .aider.chat.history.md \u589e\u52a0\u4e86 N \u884c\uff0c\u5c31\u4f1a\u628a\u8fd9\u4e9b\u884c
\u4f9d\u6b21 feed() \u8fdb\u6765\uff1b\u6211\u4eec\u6bcf\u6536\u5230\u4e00\u884c\u5c31\u68c0\u6d4b\u662f\u5426\u643a\u5e26\u201cTokens\u201d\u5b57\u6bb5\uff0c\u4e2d\u6587\u4e5f\u8981\u652f\u6301\u3002

\u63a5\u53e3\u5408\u540c BaseParser\uff0c\u5728 tokenpulse/parsers/__init__.py \u91cc\u6ce8\u518c\u5373\u53ef\u3002
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Iterable, List, Optional

from ..core.models import UsageRecord
from .base import BaseParser, ParseContext, ParseEvent, make_record_id


# ------------------------------------------------------------------ \u6b63\u5219
# \u4ee5\u4e0b\u4e24\u6761\u6b63\u5219\u5206\u522b\u9488\u5bf9 Aider \u7684\u82f1\u6587\u4e0e\u4e2d\u6587\u6837\u5f0f\u3002
# \u4ed6\u4eec\u90fd\u9700\u8981\u80fd\u4ece\u4e00\u884c\u6587\u672c\u4e2d\u63d0\u53d6\u51fa\u4e09\u4e2a\u91cf\uff1asent_tokens / received_tokens / cost_usd\u3002
# \u90e8\u5206\u6837\u672c\u4e2d cost \u53ef\u80fd\u4e3a $0.000\uff08\u514d\u8d39\u578b\u578b\u578b\uff09\u6216\u662f\u4ee5 RMB \u8868\u793a\uff0c\u4ee5\u4e0b\u6b63\u5219\u540c\u65f6\u8986\u76d6\u4e24\u79cd\u3002

# Aider \u539f\u751f\u82f1\u6587\u6837\u5f0f:
#   "Tokens: 8.5k sent, 1.2k received. Cost: $0.12 message, $1.85 session."
_RE_AIDER_EN = re.compile(
    r"Tokens?\s*:\s*"
    r"(?P<sent>[\d.,]+)\s*(?P<sent_unit>[kKmMbB]?)\s*sent\s*,\s*"
    r"(?P<received>[\d.,]+)\s*(?P<received_unit>[kKmMbB]?)\s*received"
    r"(?:\.\s*Cost\s*:\s*"
    r"(?P<currency1>[$€¥]?)\s*(?P<cost_message>[\d.,]+)\s*"
    r"(?:message|msg|turn))?"
    r"(?:\s*,\s*"
    r"(?P<currency2>[$€¥]?)\s*(?P<cost_session>[\d.,]+)\s*session)?",
    re.IGNORECASE,
)

# Aider \u4e2d\u6587\u6837\u5f0f (\u90e8\u5206\u4eba\u4f7f\u7528\u4e2d\u6587 commit hint):
#   "\u4ee3\u7406: 8.5k sent, 1.2k received\u3002\u4f1a\u8bdd\u6210\u672c: $0.12 (\u672c\u6761), $1.85 (\u4f1a\u8bdd\u7d2f\u8ba1)\u3002"
_RE_AIDER_ZH = re.compile(
    r"(?:\u4ee3\u7406|\u8bdd\u672c|\u672c\u6b21):?\s*"
    r"(?P<sent>[\d.,]+)\s*(?P<sent_unit>[kKmMbB]?)\s*sent\s*,\s*"
    r"(?P<received>[\d.,]+)\s*(?P<received_unit>[kKmMbB]?)\s*received"
    r".*?"
    r"(?P<currency1>[$€¥]?)\s*(?P<cost_message>[\d.,]+)\s*"
    r"(?:\u672c\u6761|\u672c\u6b21|message|msg|turn)?"
    r".*?"
    r"(?P<currency2>[$€¥]?)\s*(?P<cost_session>[\d.,]+)\s*"
    r"(?:\u4f1a\u8bdd|\u4f1a\u8bdd\u7d2f\u8ba1|session)?",
    re.IGNORECASE | re.DOTALL,
)


# \u5355\u4f4d\u7ffb\u500d\u8868
_UNIT_MUL = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def _to_int(num_str: str, unit: str) -> int:
    """\u628a "8.5k" \u8fd9\u6837\u7684\u4e32\u8f6c\u4e3a 8500\u3002"""
    try:
        v = float(num_str.replace(",", ""))
    except (TypeError, ValueError):
        return 0
    mul = _UNIT_MUL.get((unit or "").upper(), 1)
    return int(v * mul)


def _to_float(num_str: str) -> float:
    """\u628a "0.12" \u8fd4\u56de 0.12\u3002"""
    try:
        return float(num_str.replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


# ------------------------------------------------------------------ Parser
class AiderParser(BaseParser):
    """Aider .aider.chat.history.md \u6587\u4ef6\u89e3\u6790\u5668\u3002

    \u4f7f\u7528\u573a\u666f\uff1aAider \u4f1a\u8bdd\u8fdb\u884c\u65f6\uff0cwatchdog \u63a2\u6d4b\u5230 .aider.chat.history.md \u589e\u91cf\uff0c
    \u8c03\u7528\u8005\u4f1a\u62ff\u5230\u65b0\u589e\u884c\uff0c\u9010\u884c feed() \u8fdb\u6765\u3002\u6211\u4eec\u5728\u8fd9\u91cc\u7edf\u4e00\u8fd4\u56de ParseEvent\u3002
    """

    tool = "aider"

    # \u5982\u679c\u4e00\u4e2a\u4f1a\u8bdd\u51fa\u73b0\u591a\u4e2a commit\uff0c\u90a3\u4e48\u591a\u4e2a\u4f7f\u7528\u91cf\u6458\u8981\u90fd\u4f1a\u51fa\u73b0\u5728\u540c\u4e00\u6587\u4ef6\u4e2d\u3002
    # \u8fd9\u4e2a\u5b57\u6bb5\u662f\u4e3a\u4e86\u4e0d\u91cd\u590d\u63a8\u9001\u540c\u4e00\u884c\u3002
    def __init__(self) -> None:
        super().__init__()
        # \u4ee5 source_file \u4e3a\u952e\uff0c\u8bb0\u5f55\u5df2\u7ecf\u770b\u5230\u7684\u6700\u540e\u4e00\u884c\u884c\u53f7\uff0c\u907f\u514d\u91cd\u590d
        # (\u8c03\u7528\u8005\u53ef\u4ee5\u9009\u62e9\u4ed8\u4e0d\u540c\u7684 offset \u3002\u8fd9\u91cc\u4e3a\u7b80\u5316\u91c7\u7528 set)\u3002
        self._seen_line_hash = set()

    def feed(
        self, line: str, context: ParseContext, line_offset: int
    ) -> Iterable[ParseEvent]:
        line = (line or "").strip()
        if not line:
            return
        # \u8b66\u62a6\u91cd\u590d\u540c\u4e00\u884c
        key = (context.source_file, line)
        if key in self._seen_line_hash:
            return
        self._seen_line_hash.add(key)
        # \u9650\u5236\u8bb0\u5fc6\u96c6\u4e0d\u8981\u65e0\u9650\u589e\u957f
        if len(self._seen_line_hash) > 50_000:
            self._seen_line_hash.clear()

        # \u4f9d\u6b21\u8bd5\u82f1\u6587\u4e0e\u4e2d\u6587\u6a21\u677f
        for pattern in (_RE_AIDER_EN, _RE_AIDER_ZH):
            m = pattern.search(line)
            if not m:
                continue
            g = m.groupdict()
            sent = _to_int(g.get("sent") or "0", g.get("sent_unit") or "")
            recv = _to_int(g.get("received") or "0", g.get("received_unit") or "")
            cost_msg = _to_float(g.get("cost_message") or "0")
            cost_session = _to_float(g.get("cost_session") or "0")
            # cost_session \u662f\u4f1a\u8bdd\u7d2f\u8ba1\uff0c\u8fd9\u91cc\u53ea\u62a5\u544a\u672c\u6b21\u589e\u91cf
            # \u5982\u679c\u4ec5\u6709 cost_session \u800c\u6ca1\u6709 cost_message\uff0c\u4e0d\u8db3\u4ee5\u63a8\u65ad\u672c\u6b21\u8d39\u7528
            cost = cost_msg if cost_msg > 0 else 0.0

            # Aider \u6ca1\u6709\u72b6\u6001\u673a\uff0c\u4e3a\u6bcf\u4e2a\u5339\u914d\u5230\u7684\u884c\u751f\u6210\u4e00\u4e2a usage event
            ts = int(time.time() * 1000)
            usage = UsageRecord(
                id=make_record_id(self.tool, context.source_file, line_offset),
                ts=ts,
                tool=self.tool,
                model="aider",  # Aider \u4e0d\u4f1a\u5728\u8fd9\u91cc\u7ed9\u51fa\u6a21\u578b\u540d\uff0c\u8d4b\u4e2a\u9ed8\u8ba4
                input_tokens=sent,
                output_tokens=recv,
                cost=cost,
                session_id=context.session_id or "aider-default",
                source_file=context.source_file,
            )
            yield ParseEvent(usage=usage, model_hint="aider")
            return  # \u4e00\u884c\u53ea\u4ea7\u751f\u4e00\u4e2a event

    def finalize(self, context: ParseContext) -> Iterable[ParseEvent]:
        # Aider \u6ca1\u6709\u4ec0\u4e48 final \u72b6\u6001\u9700\u8981\u6536\u5c3e\uff0c\u4ec5\u5728\u8fd9\u91cc\u4f5c\u4e3a\u6269\u5c55\u70b9
        return ()


# \u5feb\u901f\u6f14\u793a -------------------------------------------------------------------
if __name__ == "__main__":
    p = AiderParser()
    ctx = p.new_context("/tmp/test/.aider.chat.history.md")
    samples = [
        "Tokens: 8.5k sent, 1.2k received. Cost: $0.12 message, $1.85 session.",
        "Tokens: 230 sent, 95 received. Cost: $0.003 message, $0.13 session.",
        "\u4ee3\u7406: 8.5k sent, 1.2k received\u3002\u4f1a\u8bdd\u6210\u672c: $0.12 (\u672c\u6761), $1.85 (\u4f1a\u8bdd\u7d2f\u8ba1)\u3002",
        "Commit 123abc done.",
    ]
    for i, line in enumerate(samples):
        for ev in p.feed(line, ctx, i):
            if ev.usage:
                u = ev.usage
                print(f"[{i}] {u.input_tokens} in / {u.output_tokens} out / ${u.cost:.4f}")
