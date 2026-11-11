"""到期自动下架：把 valid_until 已过的条目从检索里摘掉。

用法：
    .venv/Scripts/python.exe scripts/expire.py            # 真执行
    .venv/Scripts/python.exe scripts/expire.py --dry-run  # 只看会改哪些

线上挂 systemd timer 或宝塔计划任务，每天跑一次。
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402


def main(dry: bool) -> None:
    today = date.today().isoformat()
    sql = """
        SELECT id, question, valid_until FROM kb_item
        WHERE status = 'published'
          AND valid_until IS NOT NULL AND valid_until != ''
          AND valid_until < ?
    """
    with db.connect(write=True) as conn:
        rows = conn.execute(sql, (today,)).fetchall()
        for r in rows:
            print(f"- 下架：{r['question'][:40]}（有效期至 {r['valid_until']}）")
        if rows and not dry:
            conn.execute(
                """UPDATE kb_item SET status='expired'
                   WHERE status='published' AND valid_until IS NOT NULL
                     AND valid_until != '' AND valid_until < ?""",
                (today,),
            )
            conn.commit()
    print(f"共 {len(rows)} 条" + ("（dry-run，未改动）" if dry else " 已下架"))


if __name__ == "__main__":
    main(dry="--dry-run" in sys.argv)
