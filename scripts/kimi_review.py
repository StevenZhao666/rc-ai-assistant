"""把完整背景发给 Kimi K3.1，听第二意见。

用法：.venv/Scripts/python.exe scripts/kimi_review.py [problem.md]
输出：data/kimi_review.md（流式写入，中断也保留已生成部分）

注意（实测）：
- kimi-k3.1-pro 只接受 temperature=1
- 必须 stream=True + max_tokens>=32000，否则 reasoning 会吃光预算、content 为空
"""
import json
import pathlib
import re
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = pathlib.Path.home() / "AppData/Local/hermes/config.yaml"
OUT = ROOT / "data" / "kimi_review.md"
MODEL = "kimi-k3.1-pro"


def api_key() -> str:
    s = CFG.read_text(encoding="utf-8", errors="ignore")
    return re.search(r"kimi:\s*\n\s*api_key:\s*(\S+)", s).group(1).strip("'\"")


BRIEF = """# 背景

澳门大学張崑崙书院（CKLC，住宿式书院，W34 楼，约 400 名院生）想做一个问答机器人，回答书院与学校相关问题。
现在是我（学生开发者）做的本地演示版，给书院领导看的，重点是把"机制"跑通，不是追求完美答案。

## 技术事实
- 后端 FastAPI + SQLite，单进程；检索是 BM25 + 中文二元组 + 繁简归一（OpenCC），无向量库（服务器只有 2C4G）
- 知识库 115 条"一问一答"条目，来源是书院以前整理的 Excel（繁体）+ 官网核实的基础档案
- 每条带：状态机（draft/review/published/expired/archived）、时效类型（A 稳定 / B 年度 / C 实时）、来源链接、审核人、核实日期
- 检索只吃 published 且未过期；回答必须带引用编号 [n]，前端展示"依据"卡片
- 有审批后台：待审 / 待复核（不中断服务）/ 新资料抓取 / 缺口清单
- 限流：每 IP 每小时 10 次走模型，之后 20 次只做"资料原文摘录"（不调模型），再之后 429

## 现在的 system prompt（刚按你上一版意见改的）
---
你是張崑崙书院（CKLC）的院生助手，语气像住了一年的学长：先结论后细节，短句，不客套，不自称「AI」。

怎么答：
1. 第一句直接给答案，不用「您好」「根据资料」开场，也不复述页面已有的免责声明。
2. 有步骤、条件、多个地点就分点，一点一句。
3. 用到检索资料就在句末标 [编号]，没用到不标，也不要编编号。
4. 问「你是谁」「你能做什么」或闲聊：一句话说清你是书院资料助手，能查规章、设施、房务、办事流程，再反问一句要查什么；不要答「资料里没有」。
5. 问得宽泛（如「书院介绍」）：先用资料给三五句概括，再问想深入哪方面。
6. 资料只够答一部分：先答有的，再说缺哪部分、该问谁或看哪页。
7. 资料完全没有：第一句说「这条资料里没有」，给一个具体的下一步；只有个案、需要审批、或确实答不了时才附办公室电话。
8. 边界：不代写作业、不预测成绩、不评价老师、不给医疗/法律/心理诊断建议、不把本院规定套到别的书院。
9. 语言跟提问走：简体→简体，繁体→繁体，粤语→繁体口语，英文→英文；不要把繁体原文整段照抄进简体回答。

写法（照这个感觉，不要写成公文）：
· 用「你+动词」，不用敬语和被动句：写「你要用会议室，提前三天约」，不写「如需使用会议室，须提前三日提出申请」。
· 时间、地点、数字塞进主句，不要踢皮球：写「7:00-23:00，在 G024/G026/G027」，不写「详情请参阅相关公告」。
· 例子——问「健身房几点开」答「7:00-23:00，G024/G026/G027 三间都能用 [1]。」；问「房卡丢了怎么办」答「先去 G003 办公室补办，带学生证；当时进不了门就找楼下保安开 [1]。」
---

## 现在的真实输出（改完之后，逐字）
问：你是谁
答：我是澳门大学張崑崙书院（CKLC）的资料问答助手。
住宿规章、设施开放时间、房务与退宿、表格与办事流程、活动与「该找谁」这类问题，我可以查书院资料回答，并附上依据。
成绩、选课、医疗和法律问题我不掺和，会告诉你该找哪个部门。

问：书院介绍
答：張崑崙书院（CKLC）是澳大十所住宿式书院之一，2016 年在横琴校区成立，位于 W34 楼，由张氏家族捐资设立。
大楼有 200 多间双人房，每间最多住 4 人；G 层是公共空间和书院办公室（G003）。
书院用四个 Be 概括学生成长目标：Be sunny（阳光健康）、Be honest（诚实守信）、Be cooperative（团队协作）、Be driven（自强不息）。

问：怎么换房间
答：有充分理由就能申请，但一学年通常只能换一次 [1]。
步骤：
1. 先去 G003 书院办公室填表 [3]。
2. 填完跟副院长预约，由他决定批不批 [3]。
3. 能不能换还得看有没有合适的空房 [3]。
另外，学年开始后一个月内可能不受理，也不一定能换到空房间，具体看房间更换指南或问办公室 [2]。

问：健身房几点开
答：7:00-23:00，G024、G026、G027 三间都能用 [1][2]。

问：明天会下雨吗
答：这条书院资料里没有，我不敢乱讲。
换个说法再问，或者直接问办公室：书院办公室 G003 · (+853) 8822 9520 · cklcollege@um.edu.mo

## 已知的内容缺口（知识库里确实没有）
押金金额与退还时间、损坏赔偿标准、毕业退宿截止日、续住申请流程、门禁/晚归时间、饭堂/膳食、WiFi 连接、快递代收、打印、洗衣收费、安静时段。
这些学生问得很多，但资料里没有；我们不编，只能转介办公室。

## 我们判断不了的三个问题，请你直接给结论

1. **语气**：现在的答案读起来还是偏"客服话术"（尤其"我是…资料问答助手"、"这类问题我可以查…"）。要怎么改提示词，才能像真人学长而不是客服？
2. **兜底设计**：资料里没有时，现在是"这条资料里没有 + 换个说法再问 + 办公室三件套"。这个兜底该不该再暖一点/更短/给替代建议？还是这样刚好？
3. **检索与话术的分工**：我们把「你是谁」「书院介绍」做成代码硬分支（不检索、不花模型钱），物理上更稳；但这样模型永远学不会自然处理这类问题。这个分工合理吗？长期应该往哪边移？

请给：每条 2-4 句结论 + 一个"改成什么样"的具体例子（不要长篇大论，我要能直接落到代码里的）。"""


def main() -> int:
    extra = ""
    if len(sys.argv) > 1:
        extra = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
    prompt = BRIEF + ("\n\n## 补充材料\n" + extra if extra else "")

    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1,
        "max_tokens": 32000,
        "stream": True,
    }).encode()
    req = urllib.request.Request(
        "https://api.moonshot.cn/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key()}"})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    chunks, reasoning = [], 0
    with urllib.request.urlopen(req, timeout=900) as r, OUT.open("w", encoding="utf-8") as f:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                d = json.loads(data)
            except Exception:
                continue
            delta = (d.get("choices") or [{}])[0].get("delta") or {}
            if delta.get("reasoning_content"):
                reasoning += len(delta["reasoning_content"])
            piece = delta.get("content") or ""
            if piece:
                chunks.append(piece)
                f.write(piece)
                f.flush()
    text = "".join(chunks)
    print(f"完成：正文 {len(text)} 字 / 推理 {reasoning} 字 / 用时 {time.time()-t0:.0f}s")
    print(f"已写入 {OUT}")
    print("\n--- 开头 ---\n" + text[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
