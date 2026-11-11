"""真实用量报告：从 data/llm_usage.jsonl 算 token 与费用。

用法：
    .venv/Scripts/python.exe scripts/usage_report.py [输入单价] [输出单价]
单价单位：元 / 百万 token。默认按国内主流区间取 1.5 / 6。
"""
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "llm_usage.jsonl"


def main() -> None:
    pin = float(sys.argv[1]) if len(sys.argv) > 1 else 1.5
    pout = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0

    if not LOG.exists():
        print("还没有调用记录（data/llm_usage.jsonl 不存在）")
        return

    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        print("日志为空")
        return

    p = sum(r.get("prompt", 0) for r in rows)
    c = sum(r.get("completion", 0) for r in rows)
    days = len({r["ts"][:10] for r in rows})
    cost = p / 1e6 * pin + c / 1e6 * pout
    per_call = cost / len(rows)

    print(f"调用次数    {len(rows)}")
    print(f"输入 token  {p:,}（平均 {p//len(rows)}/次）")
    print(f"输出 token  {c:,}（平均 {c//len(rows)}/次）")
    print(f"累计费用    ¥{cost:.4f}（{pin}/{pout} 元每百万）")
    print(f"每次问答    ¥{per_call:.5f}")
    if days:
        print(f"覆盖天数    {days} 天 → 按当前强度推算月费 ¥{cost / days * 30:.2f}")
    models = Counter(r.get("model") for r in rows)
    print(f"模型分布    {dict(models)}")


if __name__ == "__main__":
    main()
