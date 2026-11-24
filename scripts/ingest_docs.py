"""把一批文件（PDF / md / txt）拆成段落存进 chunk 表，立刻可被检索。

    python scripts/ingest_docs.py inbox/                       # 目录下所有文件
    python scripts/ingest_docs.py a.pdf --version AY2026-2027
    python scripts/ingest_docs.py inbox/ --dry-run             # 只看会切出多少段

规则：
- 有「1.1 / 2.4.1」这类条款号 → 按条款切，anchor 用条款号
- 没有编号（海报、通知、FAQ）→ 按空行/段落切，每段 ≤ 900 字，anchor = p01、p02…
- 同一 source+version 重复导入先删后插，不会重复
- 只写 chunk 表，不动问答库；要不要对外，由 retriever 那边决定
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402

CLAUSE = re.compile(r"^\s*(\d+(?:\.\d+)+)\s+(.+)$")
FLAT = re.compile(r"^\s*(\d+)\.\s+(.+)$")
SUFFIX = {".pdf", ".md", ".txt"}


def extract(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        import pymupdf
        doc = pymupdf.open(str(path))
        return "\n".join(page.get_text() for page in doc)
    return path.read_text(encoding="utf-8", errors="ignore")


def split_clauses(text: str) -> list[tuple[str, str]]:
    """按条款号切；返回 [(anchor, 段落)]。少于 3 条就当没有编号。"""
    out: list[tuple[str, str]] = []
    cur_anchor, buf = "", []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = CLAUSE.match(line) or FLAT.match(line)
        if m:
            if cur_anchor and buf:
                out.append((cur_anchor, "\n".join(buf)))
            cur_anchor, buf = m.group(1), [line]
        elif cur_anchor:
            buf.append(line)
    if cur_anchor and buf:
        out.append((cur_anchor, "\n".join(buf)))
    return out if len(out) >= 3 else []


def split_paragraphs(text: str, size: int = 900) -> list[tuple[str, str]]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    blocks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 2 > size and buf:
            blocks.append(buf)
            buf = p
        else:
            buf = (buf + "\n\n" + p).strip()
    if buf:
        blocks.append(buf)
    return [(f"p{i:02d}", b) for i, b in enumerate(blocks, 1)]


def ingest(path: Path, version: str, source: str | None, dry: bool) -> int:
    text = extract(path)
    if not text.strip():
        print(f"  跳过（没有文字层）：{path.name}")
        return 0
    src = source or f"{path.stem} ({hashlib.sha1(text.encode()).hexdigest()[:12]})"
    segs = split_clauses(text) or split_paragraphs(text)
    print(f"  {path.name}: {len(text)} 字 → {len(segs)} 段（{'按条款' if split_clauses(text) else '按段落'}）")
    if dry or not segs:
        return len(segs)
    now = datetime.now().isoformat(timespec="seconds")
    with db.connect() as conn:
        conn.execute("DELETE FROM chunk WHERE source=? AND version=?", (src, version))
        conn.executemany(
            "INSERT INTO chunk (url, title, text, status, updated_at, anchor, version, source, section)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            [("", path.stem, seg, "published", now, anchor, version, src, "")
             for anchor, seg in segs])
        conn.commit()
    return len(segs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="文件或目录")
    ap.add_argument("--version", default="AY2026-2027")
    ap.add_argument("--source", default="", help="来源名，默认取文件名 + 短哈希")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    t = Path(a.target)
    files = sorted([t] if t.is_file() else [p for p in t.rglob("*") if p.suffix.lower() in SUFFIX])
    if not files:
        print("没找到 PDF / md / txt")
        return 1

    total = 0
    print(f"{'预览' if a.dry_run else '导入'}：{len(files)} 个文件，version={a.version}")
    for f in files:
        total += ingest(f, a.version, a.source or None, a.dry_run)
    if not a.dry_run:
        print(f"FTS 索引已重建：{db.rebuild_chunk_fts()} 条")
    print(f"\n合计 {total} 段" + ("（未写入）" if a.dry_run else " 已写入 chunk 表"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
