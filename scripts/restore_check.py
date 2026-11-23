"""备份恢复演练：拿最近的备份真的开一次，确认能读、能查。

    python scripts/restore_check.py                 # 用 backups/ 里最新的
    python scripts/restore_check.py backups/kb-xxx.sqlite3

只读：把备份复制到临时目录，做完整性检查 + 抽查检索，不碰线上库。
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}  {detail}")


def main() -> int:
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
    else:
        cands = sorted((ROOT / "backups").glob("kb-*.sqlite3"))
        if not cands:
            print("backups/ 里没有备份，先跑一次 start_all.bat 或手动备份")
            return 1
        src = cands[-1]

    tmp = Path(tempfile.mkdtemp(prefix="restore_"))
    dst = tmp / "kb.sqlite3"
    shutil.copy2(src, dst)
    print(f"备份：{src.name}  →  {dst}")

    con = sqlite3.connect(dst)
    ok = con.execute("PRAGMA integrity_check").fetchone()[0]
    check("完整性检查通过", ok == "ok", str(ok))

    counts = {}
    for t in ("kb_item", "chunk", "library_item", "upload_file"):
        try:
            counts[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.OperationalError:
            counts[t] = -1
    check("问答条目 > 0", counts["kb_item"] > 0, str(counts))
    check("规章条款 > 0", counts["chunk"] > 0, str(counts))

    cols = {r[1] for r in con.execute("PRAGMA table_info(chunk)")}
    if "anchor" not in cols:
        check("备份结构是当前版本", False, "旧结构缺 anchor/version，恢复后要跑迁移")
        print("这份备份太旧，别拿它当恢复依据。")
        return 1
    check("备份结构是当前版本", True)

    os.environ["DATA_DIR"] = str(tmp)
    from app import db  # noqa: E402  必须在改 DATA_DIR 之后导入

    hits = db.related_chunks("換房間", limit=3)
    check("换房间能检索到条款", bool(hits), str(len(hits)))
    rows = db.library_items(limit=5)
    check("资料库表可读", isinstance(rows, list), str(type(rows)))

    print("\n各表条数：", counts)
    print(f"{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
