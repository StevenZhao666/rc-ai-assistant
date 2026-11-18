"""给还没绑定原文的问答自动配条款（模型判断版，初稿，等人确认）。

    python scripts/autobind.py --dry-run
    python scripts/autobind.py

流程：
1. 先用词面重合挑出候选（最多 6 条），缩小范围
2. 再让模型判断：候选里哪一条真正是这条问答的依据；都不相关就回 NONE
3. 只有模型明确选中才写入，写 review_log（action=autobind），人工可改
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import answer as answer_mod  # noqa: E402
from app import db  # noqa: E402

SYS = """你在帮书院核对「问答条目」和「规章原文」的对应关系。
给你一条问答，以及若干候选条款（序号 + 条款号 + 正文）。请判断哪一条条款是这条问答的依据。
规则：
- 必须是真的在讲同一件事，不能只是都提到房间、学生这类泛词
- 拿不准，或候选里没有真正对应的，就回答 NONE
- 只输出序号（如 3）或 NONE，不要解释"""


def pick(question: str, answer: str, cands: list[dict]) -> dict | None:
    if not cands:
        return None
    listing = "\n".join(
        f"[{i}] {c['anchor']}（{(c.get('section') or '')[:30]}）：{(c['text'] or '')[:260]}"
        for i, c in enumerate(cands, 1))
    msg = f"""问答：
问题：{question}
答案：{(answer or '')[:260]}

候选条款：
{listing}

哪一条是依据？只回序号或 NONE。"""
    out = answer_mod._llm_raw([{"role": "system", "content": SYS},
                               {"role": "user", "content": msg}], max_tokens=6, temp=0)
    if not out:
        return None
    m = re.search(r"\d+", out)
    if not m:
        return None
    idx = int(m.group())
    return cands[idx - 1] if 1 <= idx <= len(cands) else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    items = [it for it in db.list_items(status="published", limit=1000)
             if not it.get("source_chunk_id")]
    if args.limit:
        items = items[:args.limit]
    print(f"未绑定条目：{len(items)} 条\n")

    bound, none = [], []
    for n, it in enumerate(items, 1):
        cands = db.related_chunks(it["question"], it.get("answer") or "", limit=6)
        choice = pick(it["question"], it.get("answer") or "", cands)
        # 模型偶尔会挑一条只在泛词上沾边的：再要求它和问题有实质重合
        if choice and len(db._tokens(it["question"]) & db._tokens((choice.get("text") or "") + " " + (choice.get("section") or ""))) < 2:
            choice = None
        if choice:
            bound.append((it, choice))
            mark = f"第 {choice['anchor']} 条（{(choice.get('section') or '')[:22]}）"
        else:
            none.append((it, cands[:1]))
            mark = "NONE（留人工）"
        print(f"[{n}/{len(items)}] #{it['id']} {it['question'][:22]} → {mark}")

    print(f"\n模型选中：{len(bound)} 条；未选中：{len(none)} 条")
    if args.dry_run:
        print("（dry-run，没有写入）")
        return

    for it, c in bound:
        db.update_item(it["id"], {"source_anchor": c["anchor"], "source_chunk_id": c["id"]})
        db.log_review(it["id"], "autobind", "auto",
                      f"自动绑定第 {c['anchor']} 条（模型判断），待人工确认",
                      before="", after=f"chunk={c['id']}")
    print(f"已写入 {len(bound)} 条。")


if __name__ == "__main__":
    main()
