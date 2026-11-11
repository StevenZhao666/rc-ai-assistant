"""模拟学生提问：批量打服务，把结果落盘，方便人工复盘。

用法：
    .venv/Scripts/python.exe scripts/simtest.py [base_url]

输出：
    屏幕：一行一题（模式 / 分数 / 答案摘要 / 命中的条目）
    文件：data/simtest_results.json
"""
import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"

QUESTIONS = [
    # 规章 / 行为
    "宿舍能养猫吗", "可以抽烟吗", "晚上几点之后不能吵", "访客可以过夜吗",
    "朋友来宿舍住一晚要多少钱", "可以在房间喝酒吗", "走廊能放鞋架吗", "房间太脏会被罚钱吗",
    # 办事流程
    "退宿要提前多久", "怎么换房间", "房卡丢了怎么办", "想投诉室友太吵",
    "怎么申请暑期住宿", "入住要带什么", "怎么申请调宿",
    # 设施
    "健身房几点开", "洗衣房在哪", "自习室开到几点", "pantry 有冰箱吗", "有没有钢琴",
    # 校务
    "add drop 什么时候", "怎么查成绩", "学费多少", "住宿费多少", "水电费怎么交",
    "电费免费额度多少", "怎么申请奖学金", "怎么续住", "PE hours 怎么上传",
    "webmail 怎么登录", "Moodle 网址", "UMRC 是什么", "七项胜任力是什么", "HA 是什么",
    "书院办公室在哪", "办公室电话多少", "办公时间",
    # 活动
    "最近有什么活动", "书院有 exchange 吗",
    # 越界 / 无关 / 敏感
    "今天食堂吃什么", "澳门哪里好玩", "帮我写一篇论文", "我室友偷我东西怎么办",
    "我心情很差想找人聊", "蔡继有书院的健身房几点开", "GPA 怎么算", "怎么申请转专业",
    "图书馆几点关门", "我这个专业要修多少学分",
    # 英文
    "What time does the gym open?", "How do I apply for room change?", "Can I keep a pet?",
    # 口语 / 错字
    "房卡不见了咋整", "宿舍能不能做饭", "电费咋算的",
]


def ask(q: str) -> dict:
    req = urllib.request.Request(
        BASE + "/api/ask",
        data=json.dumps({"question": q}).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read())
    d["_ms"] = round((time.time() - t0) * 1000)
    d["_q"] = q
    return d


def main() -> None:
    out = []
    for i, q in enumerate(QUESTIONS, 1):
        try:
            d = ask(q)
        except Exception as e:  # noqa: BLE001
            d = {"_q": q, "answer": f"<异常 {e}>", "mode": "error", "citations": [], "_ms": 0}
        out.append(d)
        cite = (d["citations"][0]["question"] if d.get("citations") else "—")
        ans = (d.get("answer") or "").replace("\n", " ")[:54]
        print(f"{i:02d} [{d.get('mode','?'):<20}] {q[:22]:24s} | {cite[:18]:20s} | {ans}")
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "simtest_results.json").write_text(
        json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"), "results": out},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n共 {len(out)} 题，结果已写 data/simtest_results.json")


if __name__ == "__main__":
    main()
