"""生成《数据整理报告》：从库 + ingest_report.json 出 Markdown。

用法：.venv/Scripts/python.exe scripts/make_report.py
输出：docs/数据整理报告-v1.md
"""
import json
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "kb.sqlite3"
REPORT = ROOT / "data" / "ingest_report.json"
OUT = ROOT / "docs" / "数据整理报告-v1.md"


def main() -> None:
    rpt = json.loads(REPORT.read_text(encoding="utf-8"))
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = list(conn.execute("SELECT * FROM kb_item"))

    by_status = Counter(r["status"] for r in rows)
    by_src = Counter(r["source_type"] for r in rows)
    by_ttl = Counter(r["ttl_type"] for r in rows)
    sources = sorted({(r["source"], r["source_url"]) for r in rows if r["source_url"]})
    warns = [(r["question"], json.loads(r["warnings"] or "[]")) for r in rows]
    warns = [(q, w) for q, w in warns if w]

    L = []
    L.append("# 知识库数据整理报告 v1\n")
    L.append(f"> 生成日期：{date.today().isoformat()}　数据源：`RC_中文正常版 (1).xlsx`（111 条）")
    L.append("> 全部由 `scripts/build_kb.py` 自动生成，规则在 `data/overrides.py` 与 `data/source_map.py`。\n")

    L.append("## 一、结果\n")
    L.append("| 指标 | 结果 |\n|---|---|")
    L.append(f"| 原始条目 | {rpt['total']} 条 |")
    L.append(f"| 已发布（可被检索） | **{by_status.get('published', 0)}** 条 |")
    L.append(f"| 已归档（不进检索） | {by_status.get('archived', 0)} 条 |")
    L.append(f"| 有官方来源 | **{by_src.get('official', 0)}** 条 |")
    L.append(f"| 外部来源（学生站，已标注非官方） | {by_src.get('external', 0)} 条 |")
    L.append(f"| 无来源（待补） | {by_src.get('unverified', 0)} 条 |")
    L.append(f"| 仍带告警 | {len(warns)} 条 |")
    L.append(f"| 本次修正 | {len(rpt['changed'])} 条 |")
    L.append("")

    L.append("## 二、分层（决定它多久复核一次）\n")
    L.append("| 类型 | 含义 | 条数 |\n|---|---|---|")
    L.append(f"| A 稳定型 | 规章条文、设施时间、联系方式，一年一变 | {by_ttl.get('A', 0)} |")
    L.append(f"| B 年度型 | 学年日历、暑期住宿、费用，每年要更新 | {by_ttl.get('B', 0)} |")
    L.append(f"| C 实时型 | 活动、通知，只给链接不生成 | {by_ttl.get('C', 0)} |")
    L.append("")

    L.append("## 三、逐条修正清单\n")
    L.append("| # | 问题 | 为什么改 | 改后（节选） |\n|---|---|---|---|")
    for i, c in enumerate(rpt["changed"], 1):
        q = c["question"].replace("|", "／")
        why = c["why"].replace("|", "／")
        after = (c.get("after") or "").replace("\n", " ").replace("|", "／")[:56]
        L.append(f"| {i} | {q} | {why} | {after} |")
    L.append("")

    L.append("## 四、仍需人工确认（带告警的条目）\n")
    L.append("| 问题 | 告警 |\n|---|---|")
    for q, w in warns:
        L.append(f"| {q[:46].replace('|', '／')} | {'；'.join(w).replace('|', '／')} |")
    L.append("")

    L.append("## 五、来源清单（点开可核）\n")
    for name, url in sources:
        L.append(f"- [{name}]({url})")
    L.append("")

    L.append("## 六、还没解决的三件事\n")
    L.append("1. **条款号**：现在只到「哪一页」，没到「第几条」。需要书院给带条款编号的规章 PDF。")
    L.append("2. **`有什麼校內諮詢app可以下載`**：答案提到 ARK ALL，但找不到官方页面，暂标无来源。")
    L.append("3. **7 条「表述模糊」**：答案是概述而非条款（如「可能需支付费用」），需要书院确认具体金额/流程。")
    L.append("")
    L.append("## 七、怎么重建\n")
    L.append("```bash\n.venv\\Scripts\\python.exe scripts\\build_kb.py \"RC_中文正常版 (1).xlsx\"\n.venv\\Scripts\\python.exe scripts\\make_report.py\n```")
    L.append("改了 `data/overrides.py` 或 `data/source_map.py` 后重跑上面两条即可，不用手改数据库。")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"已生成 {OUT}")
    print(f"发布 {by_status.get('published')} / 归档 {by_status.get('archived')} / 告警 {len(warns)}")


if __name__ == "__main__":
    main()
