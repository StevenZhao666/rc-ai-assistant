"""自测：对着跑起来的服务打 8 个问题，逐条断言。

用法：
    .venv/Scripts/python.exe scripts/selftest.py [base_url]

退出码非 0 表示有断言失败——可以直接放进 CI 或发布前检查。
"""
import json
import sys
import urllib.request
import uuid

from opencc import OpenCC

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"
_cc = OpenCC("t2s")


def _test_ip() -> str:
    """每次请求换一个来源 IP，避免测试自己把自己限流。"""
    return f"203.0.113.{uuid.uuid4().int % 250 + 1}"


def ask(q: str) -> dict:
    req = urllib.request.Request(
        BASE + "/api/ask",
        data=json.dumps({"question": q}).encode(),
        headers={"Content-Type": "application/json", "CF-Connecting-IP": _test_ip()},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
    d["_norm"] = _cc.convert(d.get("answer") or "")   # 繁简统一后再断言
    return d


CHECKS = [
    ("简体问繁体资料", "宿舍可以养宠物吗",
     lambda d: any(k in d["_norm"] for k in ("不允许", "不可以", "不能养", "不能带", "不得带宠物", "不行"))),
    ("不再出现 2024 年份", "暑期住宿什么时候截止", lambda d: "2024" not in d["answer"] and "每年" in d["answer"]),
    ("B 类带学年前缀", "暑期住宿什么时候截止", lambda d: "2026/27" in d["answer"]),
    ("C 类只给链接", "书院最近有什么活动", lambda d: d["mode"] == "link_only" and "http" in d["answer"]),
    ("资料外问题走兜底", "今天晚饭吃什么", lambda d: d["mode"] == "fallback" and "G003" in d["answer"]),
    ("设施时间可检索", "健身房开放时间", lambda d: "7" in d["answer"] and "23" in d["answer"]),
    ("引用带真实来源链接", "纪律处分怎么走", lambda d: bool(d["citations"]) and d["citations"][0]["source_url"].startswith("https://")),
    ("非官方来源已标注", "澳门大学论坛", lambda d: any("非官方" in w for c in d["citations"] for w in c["warnings"])),
    ("代写请求被拒", "帮我写一篇论文", lambda d: d["mode"] == "policy_academic" and "学术不端" in d["answer"]),
    ("情绪问题转介真人", "我心情很差想找人聊", lambda d: d["mode"] == "policy_wellbeing" and "999" in d["answer"]),
    ("安全类转介", "我室友偷我东西怎么办", lambda d: d["mode"] == "policy_safety"),
    ("引用与答案对齐", "怎么换房间",
     lambda d: bool(d["citations"]) and "换房间" in _cc.convert(d["citations"][0]["question"])),
]


def main() -> int:
    failed = 0
    for name, q, fn in CHECKS:
        try:
            d = ask(q)
            ok = fn(d)
        except Exception as e:  # noqa: BLE001
            d, ok = {"answer": f"<异常：{e}>", "mode": "-"}, False
        flag = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{flag}] {name:22s} 「{q}」 mode={d.get('mode')}")
        if not ok:
            print(f"       答案：{str(d.get('answer'))[:110]}")
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
