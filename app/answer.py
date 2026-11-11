"""回答生成：两种模式，同一个出口。

1. extractive（默认）：不调任何模型，直接把最匹配的原文拼出来 + 标来源。
   好处：本地就能跑、零成本、零幻觉，足够给领导演示「有出处」这件事。
2. llm：配了 LLM_BASE / LLM_KEY 就调 OpenAI 兼容接口，把检索结果当资料喂进去。

两种模式返回结构一样，前端不用改。
"""
import json
import re
import urllib.error
import urllib.request
from datetime import datetime

from . import config
from .profile import context_block

# 只服务张昆仑书院。学生问到别的书院时必须明确划界，不能拿本院规定冒充。
OTHER_COLLEGES = (
    "蔡繼有", "蔡继有", "曹光彪", "鄭裕彤", "郑裕彤", "霍英東", "霍英东",
    "呂志和", "吕志和", "馬萬祺", "马万祺", "滿珍", "满珍", "何鴻燊", "何鸿燊",
    "紹邦", "绍邦",
)

# 只有这些话题才需要加「适用于 2026/27 学年」前缀，避免换房、查成绩这类也被加
ANNUAL_HINTS = ("每年", "學年", "学年", "年度", "截止", "暑期", "費用", "费用",
                "住宿費", "住宿费", "續住", "续住", "申請時間", "申请时间")

# 这些不该由"书院规章问答"来答：要么违规，要么需要真人。
# 命中就走专用话术，不检索、不生成。
SAFETY_RULES = [
    (
        ("写论文", "写作业", "代写", "帮我写", "essay", "assignment", "report 代写"),
        "policy_academic",
        "这类我不做：代写作业或论文属于学术不端，书院和学校对此有明确规定。\n"
        "我可以帮的：解释规章原文、告诉你表格在哪、指路到学习支援"
        "（图书馆、RC Academic Tutorial、CTLE 的写作支持）。",
    ),
    (
        ("心情", "抑郁", "焦虑", "想死", "自杀", "撑不住", "压力大", "崩溃"),
        "policy_wellbeing",
        "这类事情不适合由问答机器人处理，但可以说清楚去哪找人：\n"
        f"· 书院办公室 / 驻院社工：{config.OFFICE_ROOM}｜{config.OFFICE_PHONE}，可以帮你约谈\n"
        "· 学生事务部（SAO）有辅导服务\n"
        "如果当下有紧急危险，请立刻拨澳门紧急电话 999，或联系书院保安。",
    ),
    (
        ("报警", "偷东西", "偷我", "被偷", "失窃", "丢东西", "打架", "受伤",
         "看医生", "医疗", "法律", "起诉"),
        "policy_safety",
        "这类涉及人身或财物安全的情况，请直接找真人处理：\n"
        "· 紧急：999（澳门）\n"
        f"· 书院保安 / 办公室：{config.OFFICE_ROOM}｜{config.OFFICE_PHONE}\n"
        "· 财物失窃建议同时报警并通知书院办公室备案。\n"
        "我不提供法律或医疗建议。",
    ),
]


def _fallback() -> dict:
    return {
        "mode": "fallback",
        "used": [],
        "text": (
            "这个问题我在书院资料里没有找到确切答案，不敢乱答。\n\n"
            f"建议直接联系书院办公室：{config.OFFICE_ROOM}｜{config.OFFICE_PHONE}｜{config.OFFICE_EMAIL}\n"
            f"办公时间：{config.OFFICE_HOURS}"
        ),
    }


def _extractive(question: str, hits: list[dict]) -> dict:
    top = hits[0]
    text = top["answer"].strip()
    related = [h for h in hits[1:] if h["score"] >= top["score"] * 0.75][:2]
    used = [1]
    if related:
        text += "\n\n另外这几条也可能相关："
        for i, r in enumerate(related, start=2):
            text += f"\n- {r['question']}：{r['answer']}"
            used.append(i)
    return {"mode": "extractive", "text": text, "used": used}


def _llm(question: str, hits: list[dict]) -> dict | None:
    """OpenAI 兼容接口。失败返回 None，让调用方退回抽取式。"""
    if not (config.LLM_BASE and config.LLM_KEY):
        return None

    ctx = "\n\n".join(
        f"[{i+1}] 问：{h['question']}\n答：{h['answer']}\n来源：{h.get('source') or '书院资料'}"
        for i, h in enumerate(hits)
    )
    system = (
        context_block()
        + f"\n你是{config.COLLEGE_NAME}的问答助手。只根据下面的资料回答，"
        "资料里没有的就说不知道，并给出办公室联系方式。"
        "不要编造，不要补充资料以外的内容。"
        "回答语言必须与提问一致：简体提问用简体回答，繁体提问用繁体，英文提问用英文；"
        "不要把资料里的繁体原文整段照抄进简体回答。"
        "凡是用到某条资料，必须在对应句子末尾标注编号，例如 [1] 或 [2]；"
        "没用到就不要标，也不许标资料里不存在的编号。"
        f"\n\n资料：\n{ctx}"
    )
    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        "temperature": 0.2,
        "max_tokens": 600,
    }
    req = urllib.request.Request(
        config.LLM_BASE + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {config.LLM_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        usage = data.get("usage") or {}
        _log_usage(config.LLM_MODEL, usage)
        text = data["choices"][0]["message"]["content"].strip()
        # 解析模型标注的 [n]，只把这些条目当引用展示
        used = sorted({int(m) for m in re.findall(r"\[(\d+)\]", text)})
        used = [i for i in used if 1 <= i <= len(hits)]
        return {
            "mode": f"llm:{data.get('model') or config.LLM_MODEL}",
            "text": text,
            "usage": usage,
            "used": used,
        }
    except Exception as e:  # noqa: BLE001
        print(f"[warn] LLM 调用失败，回退抽取式：{e}")
        return None


def _log_usage(model: str, usage: dict) -> None:
    """把每次调用的 token 用量写到 data/llm_usage.jsonl，用于算真实月费。"""
    if not usage:
        return
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "model": model,
            "prompt": usage.get("prompt_tokens", 0),
            "completion": usage.get("completion_tokens", 0),
        }
        with (config.DATA_DIR / "llm_usage.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def answer(question: str, hits: list[dict]) -> dict:
    # 一、越界问题（代写、情绪、人身安全）：不检索，直接给专用话术
    for triggers, mode, text in SAFETY_RULES:
        if any(t in question for t in triggers):
            return {"mode": mode, "text": text, "used": []}

    # 二、问到别的书院：明确划界，不拿本院规定冒充
    if any(c in question for c in OTHER_COLLEGES):
        return {
            "mode": "out_of_scope",
            "text": (
                "我只收录了张昆仑书院（CKLC）的资料，其他书院的规定可能不一样，不能拿本院的答案套过去。\n"
                "建议直接联系对应书院办公室，或查看澳大书院系统总站：https://rc.um.edu.mo/"
            ),
            "used": [],
        }

    if not hits or hits[0]["score"] < config.MIN_SCORE:
        return _fallback()

    top = hits[0]

    # C 类（活动/通知/截止日期）：只给入口，不转述。
    # 理由：这类内容今天对、明天错，转述的代价远大于给个链接。
    if top.get("ttl_type") == "C" and top.get("source_url"):
        return {
            "mode": "link_only",
            "used": [1],
            "text": (
                "这类信息变动很快（活动、通知、截止日期），我不做转述，只给入口：\n"
                f"{top['source_url']}\n\n"
                "需要确切日期的话，直接问书院办公室更快："
                f"{config.OFFICE_ROOM}｜{config.OFFICE_PHONE}"
            ),
        }

    res = _llm(question, hits) or _extractive(question, hits)

    # B 类（年度型）：只有问题本身在问年度性信息时才加前缀，
    # 否则「有没有钢琴」命中了 B 条目也会挂一句学年提示，很怪。
    if top.get("ttl_type") == "B" and any(h in question for h in ANNUAL_HINTS):
        res["text"] = (
            f"（年度性信息 · 适用于 {config.ACADEMIC_YEAR} 学年，具体以官方公告为准）\n\n"
            + res["text"]
        )
    return res


def citations(hits: list[dict]) -> list[dict]:
    """引用卡片：前端要能点开原文、看到审核状态。"""
    out = []
    for h in hits:
        out.append({
            "id": h["id"],
            "question": h["question"],
            "source": h.get("source") or "书院资料（待补来源）",
            "source_url": h.get("source_url") or "",
            "category": h.get("category") or "",
            "verified_at": h.get("verified_at") or "",
            "score": h.get("score"),
            "warnings": h.get("warnings") or [],
            "ttl_type": h.get("ttl_type"),
        })
    return out
