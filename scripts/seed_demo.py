"""生成一份虚构示例库，用来在没有任何真实资料的情况下把流程跑通。

    python scripts/seed_demo.py

内容全部虚构：书院名、电话、网页都是 example.edu，别当成真事。
想验证「审核是硬约束」，把某条改成 status='draft'，学生端立刻搜不到它。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402

DEMO = [
    {
        "question": "健身房开放时间是什么时候？",
        "answer": "每天 7:00-23:00，在 G024、G026、G027 三间。进门刷学生卡，用完把器械放回原位。",
        "category": "设施",
        "source": "书院设施页（示例）",
        "source_url": "https://example.edu/college/facilities",
        "ttl_type": "A",
    },
    {
        "question": "宿舍可以养宠物吗？",
        "answer": "不行。除导盲犬等辅助犬外，住宿生和访客都不能把宠物带进书院。",
        "category": "住宿",
        "source": "住宿规章 4.2（示例）",
        "source_url": "https://example.edu/college/handbook",
        "ttl_type": "A",
    },
    {
        "question": "怎么申请换房间？",
        "answer": "先在学生系统提交换房申请，写明原因；书院会在两周内答复。学期中只在有空位时安排。",
        "category": "住宿",
        "source": "住宿规章 6.1（示例）",
        "source_url": "https://example.edu/college/handbook",
        "ttl_type": "B",
    },
    {
        "question": "办公室在哪里？",
        "answer": "G 层 G003，工作日 9:00-13:00、14:30-17:45。电话 (+853) 0000 0000。",
        "category": "联络",
        "source": "书院联络页（示例）",
        "source_url": "https://example.edu/college/contact",
        "ttl_type": "A",
    },
    {
        "question": "访客可以过夜吗？",
        "answer": "可以，但要提前向书院申请，经院长批准，登记证件后才能留宿，最多两晚。",
        "category": "住宿",
        "source": "住宿规章 8.3（示例）",
        "source_url": "https://example.edu/college/handbook",
        "ttl_type": "A",
    },
    {
        "question": "书院的晚宴什么时候办？",
        "answer": "每学年一次，具体日期见书院公告。",
        "category": "活动",
        "source": "书院活动页（示例）",
        "source_url": "https://example.edu/college/events",
        "ttl_type": "C",  # 实时型：只该给链接，不该转述
    },
]


def main() -> None:
    db.init_db()
    existing = {row["question"] for row in db.list_items(limit=1000)}
    added = 0
    for item in DEMO:
        if item["question"] in existing:
            continue
        db.create_item({**item, "status": "published", "verified_at": "2026-01-01"})
        added += 1
    total = len(db.list_items(limit=1000))
    print(f"新增 {added} 条，库里共 {total} 条（都是虚构示例）")


if __name__ == "__main__":
    main()
