"""按天统计提问量：优先用 data/qa_log.jsonl（流水），回退到 sqlite。

用法：.venv\Scripts\python.exe scripts/usage_daily.py [天数]
"""
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROW = defaultdict(lambda: {"n": 0, "low": 0, "who": set(), "q": Counter()})


def add(ts, who, q, score):
    day = (ts or "")[:10]
    r = ROW[day]
    r["n"] += 1
    if (score or 0) < 2.5:
        r["low"] += 1
    r["who"].add(who or "?")
    r["q"][q] += 1


def main() -> int:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    jl = ROOT / "data" / "qa_log.jsonl"
    if jl.exists():
        for line in jl.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                d = json.loads(line)
            except Exception:
                continue
            add(d.get("ts"), d.get("who"), d.get("q"), d.get("score"))
    db = ROOT / "data" / "kb.sqlite3"
    if db.exists() and not ROW:
        c = sqlite3.connect(db)
        for ts, who, q, score in c.execute("SELECT ts, student_id, question, top_score FROM qa_log"):
            add(ts, who, q, score)

    if not ROW:
        print("还没有任何提问记录")
        return 0

    print(f"{'日期':12s} {'提问':>5s} {'未命中':>7s} {'访客':>5s}  最多问的")
    for day in sorted(ROW, reverse=True)[:days]:
        r = ROW[day]
        top = "、".join(f"{q}({n})" for q, n in r["q"].most_common(2))
        print(f"{day:12s} {r['n']:>5d} {r['low']:>7d} {len(r['who']):>5d}  {top[:38]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
