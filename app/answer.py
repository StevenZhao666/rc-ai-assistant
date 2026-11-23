"""回答生成：两种模式，同一个出口。

1. extractive（默认）：不调任何模型，直接把最匹配的原文拼出来 + 标来源。
   好处：本地就能跑、零成本、零幻觉，足够给领导演示「有出处」这件事。
2. llm：配了 LLM_BASE / LLM_KEY 就调 OpenAI 兼容接口，把检索结果当资料喂进去。

两种模式返回结构一样，前端不用改。
"""
import json
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

from . import config
from . import i18n
from .profile import context_block

# 只服务張崑崙书院。学生问到别的书院时必须明确划界，不能拿本院规定冒充。
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

# 「你是谁 / 你能做什么」——不该检索，也不该说不知道
META_HINTS = ("你是谁", "你是誰", "你是什么", "你是什麼", "你能做什么", "你能做什麼",
              "你可以做什么", "你可以做什麼", "你会什么", "你會什麼", "怎么用你", "怎麼用你",
              "who are you", "what can you do")

# 「书院介绍」这类泛问题——直接用基础档案讲
INTRO_HINTS = ("书院介绍", "書院介紹", "介绍一下书院", "介紹一下書院", "书院简介", "書院簡介",
               "书院是什么", "書院是什麼", "关于书院", "關於書院", "书院的历史",
               "introduce the college", "about the college", "college introduction")


LIVE_MAP = {
    "天气": "澳门气象局（smg.gov.mo）或手机天气",
    "下雨": "澳门气象局（smg.gov.mo）或手机天气",
    "落雨": "澳门气象局（smg.gov.mo）或手机天气",
    "台风": "澳门气象局（smg.gov.mo）的台风消息",
    "颱風": "澳门气象局（smg.gov.mo）的台风消息",
    "几度": "手机天气或 smg.gov.mo",
    "氣溫": "澳门气象局（smg.gov.mo）",
    "汇率": "银行官网或手机银行",
    "匯率": "银行官网或手机银行",
    "股价": "行情软件",
    "股票": "行情软件",
    "新闻": "书院公告页 cklc.rc.um.edu.mo/news-announcements/",
    "weather": "the Macao Meteorological Bureau (smg.gov.mo)",
    "exchange rate": "your bank app",
}

# 已知缺口：知识库里确实没有的事实。承认没有，给下一步，不编、不甩一长串联系方式。
GAP_MAP = {
    "押金": "押金金额和退还时间",
    "赔偿": "损坏赔偿标准",
    "赔钱": "损坏赔偿标准",
    "门禁": "门禁与晚归规定",
    "晚归": "晚归处理方式",
    "宵禁": "门禁时间",
    "饭堂": "饭堂与膳食安排",
    "膳食": "饭堂与膳食安排",
    "食堂": "饭堂与膳食安排",
    "快递": "快递代收点",
    "包裹": "快递代收点",
    "打印": "打印服务",
    "wifi": "WiFi 连接方式",
    "wi-fi": "WiFi 连接方式",
    "洗衣机收費": "洗衣收费",
    "安静": "安静时段",
    "携带": "入住携带物品清单",
    "续住": "续住申请流程",
    "截止日期": "毕业退宿截止日期",
}


def _fallback(question: str, lang: str) -> dict:
    q = question.lower()
    for k, channel in LIVE_MAP.items():
        if k in q:
            return {"mode": "fallback_live", "used": [], "text": i18n.fallback_live(lang, channel)}
    for k, topic in GAP_MAP.items():
        if k in q:
            return {"mode": "fallback_gap", "used": [], "text": i18n.fallback_gap(lang, topic)}
    return {"mode": "fallback", "used": [], "text": i18n.fallback_low(lang)}


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


_SLOTS: dict[str, "threading.Semaphore"] = {}
_COOLDOWN: dict[str, float] = {}   # 模型名 → 冷却到什么时候


def _slot(base: str, n: int) -> "threading.Semaphore":
    s = _SLOTS.get(base)
    if s is None:
        s = _SLOTS[base] = threading.Semaphore(n)
    return s


def _ask_provider(p: dict, payload: dict, timeout: int) -> dict:
    """对单个供应商发一次（被拒 thinking 时去掉重试），返回 data；内容为空抛 RuntimeError。"""
    body = dict(payload)
    body["model"] = p["model"]
    if not config.LLM_THINKING:
        body["thinking"] = {"type": "disabled"}
    try:
        data = _post_once(body, timeout, p)
    except urllib.error.HTTPError as e:
        if e.code in (400, 404, 422) and "thinking" in body:
            body.pop("thinking", None)
            data = _post_once(body, timeout, p)
        else:
            raise
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    if data.get("error") or not (msg.get("content") or "").strip():
        err = data.get("error") or {}
        raise RuntimeError(err.get("message") or "空回复")
    return data


def _post(payload: dict, timeout: int) -> dict:
    """按供应商链依次尝试：主模型 → 备用模型 → 另一家。

    有并发上限的供应商（智谱免费档 1 并发）先在本地排队 LLM_QUEUE_WAIT 秒，
    排不上就直接换下一环，别让学生干等。带 thinking 被拒时去掉重试一次。
    """
    if not config.LLM_CHAIN:
        raise RuntimeError("没有配置模型（LLM_BASE/LLM_KEY 为空）")
    errors: list[str] = []
    deadline = time.monotonic() + config.LLM_QUEUE_WAIT   # 排队总预算，不是每个模型各等一次
    for p in config.LLM_CHAIN:
        if _COOLDOWN.get(p["model"], 0) > time.time():
            errors.append(f"{p['model']}: 冷却中")
            continue
        sem = _slot(p["base"], p["limit"]) if p.get("limit") else None
        got = True
        if sem is not None:
            got = sem.acquire(timeout=max(0.5, deadline - time.monotonic()))
            if not got:
                errors.append(f"{p['model']}: 排队超时")
                continue
        try:
            data = _ask_provider(p, payload, timeout)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{p['model']}: {e}")
            if "429" in str(e) or "1305" in str(e) or "1302" in str(e) or "速率" in str(e):
                _COOLDOWN[p["model"]] = time.time() + 60   # 限流了就 60s 别再撞
            continue
        finally:
            if got and sem is not None:
                sem.release()
        if p["model"] != config.LLM_MODEL:
            print(f"[info] 主模型不可用，已切到 {p['model']}")
        return data
    raise RuntimeError("所有模型都不可用：" + "; ".join(errors[:4]))


def _post_once(body: dict, timeout: int, p: dict) -> dict:
    req = urllib.request.Request(
        p["base"] + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {p['key']}"},
    )
    with urllib.request.urlopen(req, timeout=min(timeout, config.LLM_TIMEOUT)) as r:
        return json.loads(r.read())


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
        + f"\n\n你是「崑崑」（简体字写作「崑崑」），{config.COLLEGE_NAME}的吉祥物兼资料助手。语气像住了一年的学长：先结论后细节，短句，不客套，不自称「AI」。\n"
        "怎么答：\n"
        "1. 第一句直接给答案，不用「您好」「根据资料」开场，也不复述页面已有的免责声明。\n"
        "2. 有步骤、条件、多个地点就分点，一点一句。\n"
        "3. 用到检索资料就在句末标 [编号]，没用到不标，也不要编编号。\n"
        "4. 问「你是谁」「你能做什么」或闲聊：就说自己是崑崑（简体写作崑崑），书院的吉祥物；不列能力清单、不列禁区清单；"
        "再问「你想查哪件？」。\n"
        "5. 问得宽泛（如「书院介绍」）：先用资料给三五句概括，再问想深入哪方面。\n"
        "6. 资料只够答一部分：先答有的，再说缺哪部分、该问谁或看哪页。\n"
        "7. 资料完全没有：第一句说「这条资料里没有」，给一个具体的下一步；"
        "只有个案、需要审批、或确实答不了时才附办公室电话。\n"
        "8. 边界：不代写作业、不预测成绩、不评价老师、不给医疗/法律/心理诊断建议、不把本院规定套到别的书院。\n"
        "9. 语言跟提问走：简体→简体，繁体→繁体，粤语→繁体口语，英文→英文；不要把繁体原文整段照抄进简体回答。\n"
        "写法（照这个感觉，不要写成公文）：\n"
        "· 用「你+动词」，不用敬语和被动句：写「你要用会议室，提前三天约」，不写「如需使用会议室，须提前三日提出申请」。\n"
        "· 时间、地点、数字塞进主句，不要踢皮球：写「7:00-23:00，在 G024/G026/G027」，不写「详情请参阅相关公告」。\n"
        "· 例子——问「健身房几点开」答「7:00-23:00，G024/G026/G027 三间都能用 [1]。」；"
        "问「房卡丢了怎么办」答「先去 G003 办公室补办，带学生证；当时进不了门就找楼下保安开 [1]。」\n"
        f"\n资料：\n{ctx}"
    )
    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        "temperature": 0.3,
        "max_tokens": 500,
    }
    try:
        data = _post(payload, 60)
        usage = data.get("usage") or {}
        _log_usage(data.get("model") or config.LLM_MODEL, usage)
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


# 寒暄/客套：不该检索，也不该回「查不到」
GREET_WORDS = {
    "你好", "您好", "哈啰", "哈囉", "嗨", "hi", "hello", "hey", "在吗", "在嗎",
    "早安", "早晨", "早", "晚安", "谢谢", "謝謝", "thanks", "thankyou", "thankyou",
    "再见", "再見", "bye", "好的", "ok", "okay", "你好呀", "你好啊", "hiya",
}


def is_smalltalk(q: str) -> bool:
    s = re.sub(r"[\s！!。.，,？?~～]+", "", (q or "")).lower()
    s = s.rstrip("啊呀哦喔啦吧呢")
    if s in GREET_WORDS:
        return True
    # 「你好啊/你好吗/hello there」这类短寒暄也算
    if len(s) <= 6 and any(s.startswith(g) for g in ("你好", "您好", "哈囉", "哈罗", "嗨", "hello", "hi")):
        return True
    return False


def _llm_raw(messages: list[dict], max_tokens: int = 120, temp: float = 0.3) -> str | None:
    """底层调用：给一组 messages，返回纯文本；失败返回 None。"""
    if not (config.LLM_BASE and config.LLM_KEY):
        return None
    payload = {"model": config.LLM_MODEL, "messages": messages,
               "temperature": temp, "max_tokens": max_tokens}
    try:
        data = _post(payload, 30)
        _log_usage(config.LLM_MODEL + ":gate", data.get("usage") or {})
        return (data["choices"][0]["message"]["content"] or "").strip()
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 轻量调用失败：{e}")
        return None


GATE_SYS = """你是一个意图分类器。判断用户这句话是否需要查阅「书院资料库」才能回答。
需要查资料（输出 1）：问书院/学校的具体信息，例如规章、住宿、设施、开放时间、费用、表格、办事流程、活动、联系方式。
不需要查资料（输出 0）：问候、寒暄、感谢、告别、问你是谁/你能做什么、表达情绪、闲聊、与书院无关的问题（天气、新闻、作业题）。
只输出一个字符：1 或 0。"""


def needs_kb(question: str) -> bool | None:
    """让模型判一次：需不需要查资料。没模型可用时返回 None（调用方退回关键词）。"""
    out = _llm_raw([{"role": "system", "content": GATE_SYS},
                    {"role": "user", "content": question}], max_tokens=8, temp=0)
    if out is None:
        return None
    return out.strip().startswith("1")


def chat_reply(question: str, lang: str) -> str:
    """闲聊直接由模型生成一句自然的回应，不查资料、不列能力清单。"""
    sys = (
        "你是崑崑（简体写作崑崑），澳门大学張崑崙书院的吉祥物兼助手。"
        "现在对方在寒暄或闲聊，直接自然回应一句到两句，语气像熟悉的学长；"
        "不要提「资料库」，不要罗列能力清单，不要每句都让人去问办公室。"
        "如果对方问你是谁，就说自己是崑崑（简体写作崑崑）、书院的吉祥物。"
        "硬规矩：不编造任何事实（天气、价格、时间、新闻、成绩都不许猜）；"
        "做不到的事不要答应（看代码、写作业、预测成绩、查个人记录）；"
        "被问到这类就说自己查不了或帮不上，最多给一个方向。"
        "语言跟提问严格一致：简体提问必须用简体汉字回答，不要夹粤语字（唔/嘅/咗/喺）；"
        "粤语口语提问才用繁体口语；英文提问用英文。"
    )
    if lang == "zh-Hant":
        sys += ("对方用繁体中文提问：整段回答必须全部是繁体字，名字写「崑崑」，"
                "一个简体字都不许出现；对方用粤语口语就用繁体口语回。")
    elif lang == "en":
        sys += "Answer in English only."
    else:
        sys += "对方用简体中文提问：整段回答必须全部是简体字，名字写「崑崑」，不要出现繁体字。"
    out = _llm_raw([{"role": "system", "content": sys},
                    {"role": "user", "content": question}], max_tokens=180, temp=0.6)
    if out:
        return out
    return i18n.smalltalk(lang)


def _intro_from_kb(lang: str) -> dict | None:
    """书院介绍：从已发布的「书院基础档案」条目拼，带真实引用，不另写一套事实。"""
    from . import db
    items = [i for i in db.list_items("published")
             if (i.get("category") or "") == "书院基础档案"]
    if len(items) < 2:
        return None
    order = ("在哪棟樓", "什麼時候成立", "多少房間", "精神")
    picked = []
    for kw in order:
        for it in items:
            if kw in (it.get("question") or "") and it not in picked:
                picked.append(it)
                break
    if len(picked) < 2:
        picked = items[:3]

    def _clean(x: str) -> str:
        x = x.replace("在横琴校区澳门大学横琴校区", "在横琴校区")
        x = x.replace("澳门大学横琴校区", "横琴校区")
        if lang == "zh-Hans":
            try:
                from opencc import OpenCC
                x = OpenCC("t2s").convert(x)
            except Exception:
                pass
        return x.strip().rstrip("。")

    parts = []
    for i, it in enumerate(picked, start=1):
        parts.append(_clean(it.get("answer") or "") + "。 [" + str(i) + "]")
    tail = {"en": " Want more on any part?",
            "zh-Hant": " 想細問邊部分？",
            "zh-Hans": " 想细问哪部分？"}[lang]
    text = "\n".join(parts) + tail
    cites = [{"id": it["id"], "question": it["question"], "source": it.get("source"),
              "source_url": it.get("source_url"), "warnings": []} for it in picked]
    return {"mode": "intro", "text": text, "used": [], "sources": cites}


def answer(question: str, hits: list[dict], allow_llm: bool = True) -> dict:
    """对外入口：算完回答后统一字形（繁问繁答、简问简答），再返回。"""
    out = _answer_impl(question, hits, allow_llm)
    if out.get("text"):
        out["text"] = i18n.normalize_script(out["text"], i18n.detect_lang(question))
    return out


def _answer_impl(question: str, hits: list[dict], allow_llm: bool = True) -> dict:
    lang = i18n.detect_lang(question)

    # 一、越界问题（必须最先判：代写/医疗/情绪/安全不能被当成闲聊）（急救、医疗、代写、情绪、人身安全）：不检索，直接给专用话术
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


    # 零、寒暄：你好 / 谢谢 / 在吗 —— 像人一样回一句，别查资料
    # 实时信息（天气等）和确知没有的资料，先挡掉，绝不让模型自由发挥
    ql = question.lower()
    for k, channel in LIVE_MAP.items():
        if k in ql:
            return {"mode": "fallback_live", "used": [],
                    "text": i18n.fallback_live(lang, channel)}
    for k, topic in GAP_MAP.items():
        if k in ql and k not in ("续住", "截止日期"):
            return {"mode": "fallback_gap", "used": [],
                    "text": i18n.fallback_gap(lang, topic)}

    strong_hit = bool(hits) and hits[0].get("score", 0) >= config.MIN_SCORE
    if strong_hit:
        need = True                      # 资料库里明明有，就别判成闲聊
    elif allow_llm:
        need = needs_kb(question)
    else:
        need = None

    if need is False:
        return {"mode": "chat", "text": chat_reply(question, lang), "used": []}
    if need is None and is_smalltalk(question):
        s0 = re.sub(r"[\s！!。.，,？?~～]+", "", question).lower()
        text = i18n.thanks_reply(lang) if s0 in ("谢谢", "謝謝", "thanks", "thankyou", "唔该", "唔該") else i18n.smalltalk(lang)
        return {"mode": "chat", "text": text, "used": []}

    # 零、问「你是谁」和「书院介绍」：不该检索，也不该说不知道
    if any(h in question.lower() for h in META_HINTS):
        return {"mode": "meta", "text": i18n.meta_identity(lang), "used": []}
    if any(h in question.lower() for h in INTRO_HINTS):
        return _intro_from_kb(lang) or {"mode": "intro", "text": i18n.college_intro(lang), "used": []}

    if not hits or hits[0]["score"] < config.MIN_SCORE:
        return _fallback(question, lang)

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
            "answer": (h.get("answer") or "")[:600],
        })
    return out
