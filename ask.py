"""命令行问书院：一句话进，带依据的答案出。

    python ask.py "書院能不能養寵物"
    python ask.py --url http://159.75.225.125/ai "洗衣房在哪一层"
    python ask.py --json "换房间"

给 dsh / 其他 agent 用的时候，直接调它，把输出原样转述即可。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("RC_AI_BASE", "http://127.0.0.1:8001").rstrip("/")
SID = os.environ.get("RC_AI_SID", "uc88888")       # 虚构学号，只用于命令行


def ask(question: str, base: str, sid: str, timeout: int = 120) -> dict:
    body = json.dumps({"question": question}).encode("utf-8")
    req = urllib.request.Request(
        base + "/api/ask", data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Student-Id": sid,
                 "X-Session-Id": "cli"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def render(d: dict) -> str:
    out = [d.get("answer", "").strip()]
    cites = d.get("citations") or []
    if cites:
        out.append("")
        for i, c in enumerate(cites, 1):
            title = c.get("question") or c.get("title") or ""
            out.append(f"依据 {i} · 条目 {c.get('id')} · {title}")
            if c.get("source"):
                out.append(f"        来源：{c['source']}")
    if d.get("warnings"):
        out.append("")
        out.extend(f"注意：{w}" for w in d["warnings"])
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="问书院（带依据）")
    ap.add_argument("question", nargs="+", help="用自然语言问")
    ap.add_argument("--url", default=BASE, help=f"服务地址，默认 {BASE}")
    ap.add_argument("--sid", default=SID, help="学号（虚构即可），只影响限额计数")
    ap.add_argument("--json", action="store_true", help="输出原始 JSON")
    ap.add_argument("--timeout", type=int, default=120)
    a = ap.parse_args()
    q = " ".join(a.question).strip()
    if not q:
        print("要问什么？", file=sys.stderr)
        return 2
    try:
        d = ask(q, a.url.rstrip("/"), a.sid, a.timeout)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        print(f"服务返回 {e.code}：{detail}", file=sys.stderr)
        if e.code == 429:
            print("这个小时的额度用完了，过一会儿再问，或换 --sid。", file=sys.stderr)
        return 1
    except Exception as e:                                   # noqa: BLE001
        print(f"连不上 {a.url}（{type(e).__name__}）。服务起了吗？"
              f"\n本机可跑 scripts/start_all.bat，服务器上应已常驻。", file=sys.stderr)
        return 1
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else render(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
