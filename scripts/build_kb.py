"""构建知识库：Excel → 加工规则 → SQLite。

用法：
    .venv/Scripts/python.exe scripts/build_kb.py "<xlsx 路径>"

Excel 是原始输入，data/source_map.py 与 data/overrides.py 是加工规则。
每次重建都重新套一遍，所以修正是可重复、可审计的，不是手改数据库。

处理顺序：
  1. 读 Excel
  2. 套逐条修正（overrides）
  3. 指派来源（source_map）
  4. 自动检查（空答案 / 往年 / 非官方 / 重复 / 模糊）
  5. 定分层（A 稳定 / B 年度 / C 实时）
  6. 写库 + 出报告
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data"))

from app import db  # noqa: E402
from app.profile import PROFILE_ENTRIES  # noqa: E402
try:  # 修正层是可选的：公开框架不带真实题库的规则文件
    from overrides import ARCHIVE, OVERRIDES  # noqa: E402
except ImportError:
    ARCHIVE, OVERRIDES = [], []

try:
    from source_map import pick as pick_source  # noqa: E402
except ImportError:
    def pick_source(question: str):  # 没有来源表时一律标 unverified
        return {"url": "", "title": "未指派来源", "type": "unverified"}

BAD_YEARS = re.compile(r"20(1\d|2[0-4])")
VAGUE = ("通常", "一般", "原则上", "原則上")
NON_OFFICIAL = ("umeh.top", "whole.umeh")
REALTIME = ("活動", "活动", "截止", "報名", "报名", "暑期", "交流")
YEARLY = ("學年", "学年", "每年", "add", "drop", "住宿費", "暑期")


def classify(question: str, answer: str) -> str:
    """A 稳定 / B 年度 / C 实时。只看问题：答案里的「每学年一次」会把换房误判成年度型。"""
    if any(w in question for w in ("活動", "活动", "近期", "最近", "最新通知", "活動通知")):
        return "C"
    if any(w in question for w in ("每年", "學年", "学年", "年度", "截止", "暑期",
                                   "費用", "费用", "續住", "续住", "申請時間", "申请时间")):
        return "B"
    return "A"


def find_override(question: str) -> tuple[dict, str]:
    for ov in OVERRIDES:
        if ov["match"] in question:
            return ov, ov["why"]
    return {}, ""


def load_rows(xlsx_path: Path) -> list[tuple[str, str]]:
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = []
    for q, a in ws.iter_rows(min_row=2, max_col=2, values_only=True):
        if q is None:
            continue
        rows.append((str(q).strip(), (str(a).strip() if a is not None else "")))
    return rows


def main(xlsx_path: str) -> None:
    db.init_db()
    rows = load_rows(Path(xlsx_path))

    seen: dict[str, int] = {}
    changes: list[dict] = []
    counters: dict[str, int] = {"published": 0, "draft": 0, "archived": 0}
    src_types: dict[str, int] = {"official": 0, "external": 0, "unverified": 0}
    ttl_counts: dict[str, int] = {"A": 0, "B": 0, "C": 0}
    warn_total = 0

    with db.connect(write=True) as conn:
        conn.execute("DROP TABLE IF EXISTS kb_item")
        conn.executescript(db.SCHEMA)
        conn.execute("DELETE FROM kb_item")

        for question, answer in rows:
            raw_ov, why = find_override(question)
            fields = raw_ov.get("apply", {}) if raw_ov else {}
            new_answer = fields.get("answer", answer)
            status = fields.get("status", "published")
            ttl = fields.get("ttl_type") or classify(question, new_answer)
            src = pick_source(question)
            if fields.get("source_type"):
                src = dict(src, type=fields["source_type"])

            warnings: list[str] = []
            if not new_answer.strip():
                warnings.append("答案为空，需补写")
                status = "draft"
            if BAD_YEARS.search(question + new_answer) and not fields:
                warnings.append("含往年（2010-2024）信息，需确认是否仍有效")
            if any(k in new_answer for k in NON_OFFICIAL):
                warnings.append("引用学生自建站，非官方")
            if (new_answer and not fields
                    and any(w in new_answer for w in VAGUE)
                    and len(new_answer) < 100
                    and not re.search(r"\d", new_answer)
                    and "http" not in new_answer):
                warnings.append("表述模糊，缺具体条款/链接")
            if question in seen:
                warnings.append("重复条目，已合并（保留首条）")
                status = "archived"
            seen[question] = seen.get(question, 0) + 1

            for arc in ARCHIVE:
                if arc["match"] in question:
                    status = "archived"
                    warnings.append(f"归档：{arc['why']}")
                    why = arc["why"]

            if why:
                changes.append({
                    "question": question,
                    "why": why,
                    "before": answer[:60],
                    "after": new_answer[:60],
                })
            if warnings:
                warn_total += 1
            counters[status] = counters.get(status, 0) + 1
            src_types[src["type"]] = src_types.get(src["type"], 0) + 1
            ttl_counts[ttl] = ttl_counts.get(ttl, 0) + 1

            conn.execute(
                """INSERT INTO kb_item
                   (question, answer, category, source, source_url, source_type, status,
                    ttl_type, audience, owner, reviewer, verified_at, valid_until,
                    warnings, note, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    question, new_answer, "书院规章/设施/校务",
                    src["name"], src["url"], src["type"], status,
                    ttl, "all", "", "", "", "",
                    json.dumps(warnings, ensure_ascii=False), why,
                    date.today().isoformat(),
                ),
            )
        # 书院基础档案：常用事实直接进库，保证「书院在哪/什么时候成立」这类问题答得上
        for q, a, src_name, src_url in PROFILE_ENTRIES:
            conn.execute(
                """INSERT INTO kb_item
                   (question, answer, category, source, source_url, source_type, status,
                    ttl_type, audience, owner, reviewer, verified_at, valid_until,
                    warnings, note, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    q, a, "书院基础档案", src_name, src_url, "official", "published",
                    "A", "all", "", "", date.today().isoformat(), "",
                    "[]", "来自书院官网", date.today().isoformat(),
                ),
            )
            counters["published"] = counters.get("published", 0) + 1
            src_types["official"] = src_types.get("official", 0) + 1
            ttl_counts["A"] = ttl_counts.get("A", 0) + 1

        conn.commit()

    report = {
        "total": len(rows),
        "status": counters,
        "source_type": src_types,
        "ttl_type": ttl_counts,
        "with_warnings": warn_total,
        "changed": changes,
        "generated_at": date.today().isoformat(),
    }
    (ROOT / "data" / "ingest_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"导入 {len(rows)} 条")
    print(f"  状态：{counters}")
    print(f"  来源：{src_types}")
    print(f"  分层：{ttl_counts}")
    print(f"  有告警：{warn_total}    已修正：{len(changes)}")
    print("  报告：data/ingest_report.json")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/build_kb.py <xlsx路径>")
        raise SystemExit(1)
    main(sys.argv[1])
