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
from . import i18n
from .profile import context_block

# 只服务张昆仑书院。学生问到别的书院时必须明确划界，不能拿本院规定冒充。
OTHER_COLLEGES = (
    "蔡繼有", "蔡继有", "曹光彪", "鄭裕彤", "郑裕彤", "霍英東", "霍英东",
    "呂志和", "吕志和", "馬萬祺", "马万祺", "滿珍", "满珍", "何鴻燊", "何鸿燊",
    "紹邦", "绍邦",
    # 英文提问时同样要划界（测试里英文问「another college」被当成普通未知问题）
    "cytc", "ckpc", "cytc", "lcc", "shc", "mcm", "spc", "mmk", "cky",
    "choi kai yau", "cheng yu tung", "lui che woo", "stanley ho",
    "pearl jubilee", "moon chun memorial", "shiu pong", "chao kuang piu",
    "another college", "other college", "other hall", "another hall",
)

# 只有这些话题才需要加「适用于 2026/27 学年」前缀，避免换房、查成绩这类也被加
ANNUAL_HINTS = ("每年", "學年", "学年", "年度", "截止", "暑期", "費用", "费用",
                "住宿費", "住宿费", "續住", "续住", "申請時間", "申请时间")

# 这些不该由"书院规章问答"来答：要么违规，要么需要真人。
# 命中就走专用话术（按提问语言出三套文案），不检索、不生成。
SAFETY_RULES = [
    (
        ("火警", "火災", "火灾", "走火", "急救", "急診", "急诊", "救护车", "救護車",
         "急救电话", "999", "110", "119", "救命", "晕倒", "暈倒", "流血不止",
         "fire alarm", "ambulance", "emergency"),
        "emergency",
    ),
    (
        ("吃什么药", "吃什麼藥", "食咩藥", "用药", "用藥", "药物", "藥物", "剂量", "劑量",
         "发烧", "發燒", "咳嗽", "看医生", "看醫生", "medicine", "dosage", "symptoms"),
        "medical",
    ),
    (
        ("写论文", "写作业", "代写", "帮我写", "寫論文", "寫作業", "代寫", "幫我寫",
         "essay", "assignment"),
        "academic",
    ),
    (
        ("心情", "抑郁", "抑鬱", "焦虑", "焦慮", "想死", "自杀", "自殺", "撑不住", "撐不住",
         "压力大", "壓力大", "崩溃", "崩潰", "活着没意思", "活著沒意思"),
        "wellbeing",
    ),
    (
        ("报警", "報警", "偷东西", "偷東西", "偷我", "被偷", "失窃", "失竊", "丢东西",
         "打架", "受伤", "受傷", "法律", "起诉", "起訴", "律师", "律師"),
        "safety",
    ),
]

# 只有问题本身在问"活动/通知"时才走 link_only。
# 之前只要命中一条 C 类条目就只给链接，导致「書院內禁止賭博嗎」「check-in 到幾點」被误判。
ACTIVITY_HINTS = ("活動", "活动", "通知", "最近", "近期", "最新", "有咩",
                  "event", "events", "news", "calendar")


def _fallback(lang: str) -> dict:
    return {
        "mode": "fallback",
        "used": [],
        "text": i18n.fallback(lang),
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
        "用粤语口语提问（唔、嘅、喺、咗、邊度）时，用繁体中文回答，不要转成简体；"
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


def answer(question: str, hits: list[dict], allow_llm: bool = True) -> dict:
    lang = i18n.detect_lang(question)

    # 一、越界问题（急救、医疗、代写、情绪、人身安全）：不检索，直接给专用话术
    for triggers, kind in SAFETY_RULES:
        if any(t in question.lower() if t.isascii() else t in question for t in triggers):
            # 火警演习、急救箱位置这类不是真紧急，不该触发"立刻拨 999"
            if kind == "emergency" and any(x in question for x in
                                           ("演習", "演习", "drill", "急救箱", "急救課程",
                                            "急救课程", "AED", "AED機")):
                continue
            return {"mode": f"policy_{kind}", "text": i18n.policy(kind, lang), "used": []}

    # 二、问到别的书院：明确划界，不拿本院规定冒充
    if any(c in question for c in OTHER_COLLEGES):
        return {
            "mode": "out_of_scope",
            "text": i18n.out_of_scope(lang),
            "used": [],
        }

    if not hits or hits[0]["score"] < config.MIN_SCORE:
        return _fallback(lang)

    top = hits[0]

    # C 类（活动/通知/截止日期）：只给入口，不转述。
    # 但必须问题本身在问活动——否则「书院禁止赌博吗」命中 C 条目也会被塞一条新闻链接。
    if (top.get("ttl_type") == "C" and top.get("source_url")
            and any(h in question for h in ACTIVITY_HINTS)):
        return {
            "mode": "link_only",
            "used": [1],
            "text": i18n.link_only(lang, top["source_url"]),
        }

    # allow_llm=False：本小时模型额度用完了，只做资料摘录，一分钱不花
    res = (_llm(question, hits) if allow_llm else None) or _extractive(question, hits)

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
