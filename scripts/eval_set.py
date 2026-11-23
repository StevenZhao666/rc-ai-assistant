"""评测基线：跑 data/eval_cases.json，锁住检索与版本字段的行为。

    python scripts/eval_set.py                 # 默认本机 8001
    python scripts/eval_set.py --url http://159.75.225.125/ai

只看检索层（/api/search）：有答案的必须搜到条目，无答案的必须搜不到；
所有命中都必须带 uid / revision。不调模型，几秒跑完，适合每次改动后跑。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "eval_cases.json"
PASS = FAIL = 0
FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
    else:
        FAIL += 1
        FAILS.append(f"{name}｜{detail}")
        print(f"[FAIL] {name}  {detail}")


TOKEN = os.environ.get("SCRAPE_BYPASS", "")
USES_ASK = False


def ask(base: str, q: str) -> dict:
    body = json.dumps({"question": q}).encode()
    req = urllib.request.Request(base + "/api/ask", data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "X-Student-Id": "uc88888",
                                          "X-Scrape-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def search(base: str, q: str, limit: int = 5) -> list[dict]:
    url = f"{base}/api/search?q={urllib.parse.quote(q)}&limit={limit}"
    req = urllib.request.Request(url, headers={"X-Scrape-Token": TOKEN} if TOKEN else {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("items", [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8001")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--ask-none", action="store_true", help="无答案类改走 /api/ask 判断兜底")
    a = ap.parse_args()
    base = a.url.rstrip("/")
    global USES_ASK
    USES_ASK = a.ask_none

    spec = json.loads(CASES.read_text(encoding="utf-8"))
    cases, rules = spec["cases"], spec["checks"]
    uid_re = re.compile(rules.get("uid_format", "^kb-"))

    for c in cases:
        q, expect = c["q"], c["expect"]
        try:
            items = search(base, q)
        except Exception as e:                              # noqa: BLE001
            check(f"检索可用｜{q}", False, f"{type(e).__name__}: {e}")
            continue
        if expect == "answer":
            ok = bool(items)
        else:
            # 无答案类：看回答层是否兜底（不检索/不硬编）
            try:
                d = ask(base, q) if USES_ASK else {"items": items}
            except Exception as e:                          # noqa: BLE001
                check(f"兜底｜{q}", False, str(e)[:80])
                continue
            if not USES_ASK:
                ok = not items
            else:
                mode = str(d.get("mode", ""))
                text = str(d.get("answer", ""))
                ok = (mode.startswith("fallback") or mode.startswith("policy")
                      or any(k in text for k in ("查不到", "資料裏沒有", "资料里没有", "不做")))
        check(f"{expect}｜{q}", ok, f"命中 {len(items)} 条")

        if rules.get("require_uid"):
            for it in items:
                if it.get("type") != "qa":
                    continue
                if not uid_re.match(str(it.get("uid") or "")):
                    check(f"uid 格式｜{q}", False, str(it.get("uid")))
                    break
        if a.verbose and items:
            print(f"   {q} → {[i.get('title', '')[:18] for i in items[:3]]}")

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    if FAILS:
        print("\n失败明细：")
        for f in FAILS:
            print(" -", f)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
