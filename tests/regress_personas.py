"""回归：把五份黑盒报告里失败的问法逐条重打，比对 mode 与关键事实。"""
import json
import re
import sys
import urllib.request

BASE = "http://127.0.0.1:8001/api/ask"

CASES = [
    # (问句, 期望 mode 前缀, 必须出现 / 不得出现)  —— 断言前统一转简体，避免字形误判
    ("我朋友周末来看我 能睡我房间吗", "llm", ["访客", "院长"], []),
    ("可唔可以喺宿舍養隻貓？", "llm", ["宠物"], []),
    ("室內食煙得唔得？", "llm", ["吸烟"], []),
    ("同房友打麻雀賭錢得唔得？", "llm", ["赌博"], []),
    ("書院內禁止賭博嗎？", "llm", ["赌博"], []),
    ("書院有甚麼設施？", "llm", ["设施"], []),
    ("How and where do I check in, what do I bring, until what time is the front desk open?",
     "llm", ["check"], []),
    ("If there is an emergency at 3am, like a fire alarm, who do I call?", "policy_emergency", ["999"], []),
    ("宿舍几点关门？晚归怎么办？", "", [], []),
    ("健身房几点开", "llm", ["7:00", "23:00"], []),
    ("书院最近有什么活动", "link_only", [], []),
    ("What is the wifi network name and password?", "llm", [], []),
    ("我发烧39度还咳嗽，应该吃什么药？", "policy_medical", ["999"], []),
    ("帮我写一篇论文", "policy_academic", ["学术"], []),
    ("蔡继有书院的住宿规定是什么？", "out_of_scope", ["rc.um.edu.mo"], []),
    # 回归：火警演习不该触发紧急话术
    ("书院下个月的火警演习是什么时候？", "llm", [], ["立即拨"]),
]

def ask(q):
    req = urllib.request.Request(BASE, data=json.dumps({"question": q}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


from opencc import OpenCC  # noqa: E402
_cc = OpenCC("t2s")


def simp(s: str) -> str:
    return _cc.convert(s or "")

ok = fail = 0
for q, want_mode, must, mustnot in CASES:
    try:
        d = ask(q)
    except Exception as e:
        print(f"ERR  {q[:40]}  {e}")
        fail += 1
        continue
    mode, ans, cites = d["mode"], d["answer"], d.get("citations", [])
    flat = simp(ans).lower()
    problems = []
    if want_mode and not mode.startswith(want_mode):
        problems.append(f"mode={mode} 期望 {want_mode}")
    for m in must:
        if simp(m).lower() not in flat:
            problems.append(f"缺「{m}」")
    for m in mustnot:
        if simp(m).lower() in flat:
            problems.append(f"不该出现「{m}」")
    # 引用编号不能越界
    nums = {int(x) for x in re.findall(r"\[(\d+)\]", ans)}
    if nums and (max(nums) > len(cites) or len(cites) == 0):
        problems.append(f"编号越界 {sorted(nums)} vs {len(cites)} 卡")
    status = "PASS" if not problems else "FAIL"
    if problems:
        fail += 1
    else:
        ok += 1
    print(f"{status} {mode:18s} {q[:34]:36s} {'; '.join(problems)}")
    if problems:
        print(f"      → {ans[:110].replace(chr(10), ' ')}")

print(f"\n{ok} pass / {fail} fail / {len(CASES)} total")
sys.exit(0 if fail == 0 else 1)
