"""把规章 PDF 拆成「段落级原文」存进 chunk 表，供审核时对照。

    python scripts/ingest_pdf.py "D:/浏览器下载/xxx.pdf" --version AY2026-2027 --source "CKLC Student Handbook"

要点：
- 按条款号（1.1 / 2.4.1）切段，保留条款号作为 anchor
- 原文一字不改，只做换行整理；英文与中文各自成段
- 同一份文件重复导入时，先按 source+version+anchor 覆盖，不产生重复
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402

CLAUSE = re.compile(r"^\s*(\d+(?:\.\d+)+)\s+(.*)$")
SECTION = re.compile(r"^\s*(\d+)\.\s+([A-Z][^\n]{2,60})$")
NOISE = re.compile(r"^P\s*a\s*g\s*e\s*\|\s*\d+|^Cheong Kun Lun College STUDENT HANDBOOK$")


def clean_lines(page_text: str) -> list[str]:
    out = []
    for raw in page_text.splitlines():
        line = raw.strip()
        if not line or NOISE.search(line):
            continue
        out.append(line)
    return out


def variant_of(text: str) -> str:
    return "zh" if any("一" <= ch <= "鿿" for ch in text) else "en"


def parse(pdf_path: Path) -> list[dict]:
    doc = pymupdf.open(pdf_path)
    clauses: list[dict] = []
    section = ""
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current and current["text"].strip():
            current["text"] = current["text"].strip()
            current["variant"] = variant_of(current["text"])
            clauses.append(current)
        current = None

    for page in doc:
        for line in clean_lines(page.get_text()):
            m_sec = SECTION.match(line)
            if m_sec and "." not in m_sec.group(1):
                flush()
                section = f"{m_sec.group(1)}. {m_sec.group(2).strip()}"
                continue
            m = CLAUSE.match(line)
            if m:
                flush()
                current = {"anchor": m.group(1), "section": section, "text": m.group(2)}
                continue
            if current:
                # 续行：中文行直接拼，英文行补空格
                joiner = "" if re.search(r"[\u4e00-\u9fff]$", current["text"]) else " "
                current["text"] += joiner + line
    flush()
    return clauses


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--version", default="", help="例如 AY2026-2027")
    ap.add_argument("--source", default="", help="例如 CKLC Student Handbook")
    ap.add_argument("--url", default="", help="官方页面链接（可空）")
    ap.add_argument("--replace", action="store_true", help="先删掉同一来源+版本的旧条款，再导入")
    args = ap.parse_args()

    path = Path(args.pdf)
    if not path.exists():
        sys.exit(f"找不到文件：{path}")

    clauses = parse(path)
    if not clauses:
        sys.exit("没切出条款，检查 PDF 是否是扫描件")

    db.init_db()
    digest = hashlib.sha1(path.read_bytes()).hexdigest()[:12]
    title = args.source or path.stem
    version = args.version or datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().isoformat(timespec="seconds")

    added = updated = deleted = 0
    with db.connect(write=True) as conn:
        if args.replace:
            deleted = conn.execute("DELETE FROM chunk WHERE title=? AND version=?",
                                   (title, version)).rowcount
        for c in clauses:
            text = c["text"]
            if len(text) < 8:
                continue
            h = hashlib.sha1(f"{c.get('section','')}|{c['anchor']}|{c.get('variant','')}|{text}".encode()).hexdigest()[:16]
            row = conn.execute(
                "SELECT id FROM chunk WHERE title=? AND version=? AND hash=?",
                (title, version, h)).fetchone()
            if row:
                conn.execute("UPDATE chunk SET text=?, updated_at=? WHERE id=?",
                             (text, now, row[0]))
                updated += 1
            else:
                conn.execute(
                    "INSERT INTO chunk (url, title, text, status, updated_at, anchor, version, source,"
                    " section, variant, hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (args.url, title, text, "published", now, c["anchor"], version,
                     f"{title} · {version} ({digest})", c.get("section") or "", c.get("variant") or "", h))
                added += 1
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM chunk").fetchone()[0]

    print(f"文件：{path.name}（{path.stat().st_size // 1024} KB）")
    print(f"切出条款：{len(clauses)} 条（删除旧 {deleted} / 新增 {added} / 更新 {updated}）")
    print(f"chunk 表共 {total} 条")
    for c in clauses[:3]:
        print(f"  [{c['anchor']}] {c['text'][:60]}")


if __name__ == "__main__":
    main()
