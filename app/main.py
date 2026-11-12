"""FastAPI 入口。

本地跑：  uvicorn app.main:app --reload --port 8001
线上跑：  uvicorn app.main:app --host 127.0.0.1 --port 8000   （由 Apache 反代 /ai）
"""
from pathlib import Path

import os
import re
import time
from collections import deque

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import answer as answer_mod
from . import config, db
from .auth import User, get_current_user
from .retrieve import Retriever
from .review import router as review_router
from .review import set_reload

app = FastAPI(title="RC AI Assistant", version="0.1.0")
app.include_router(review_router)
app.mount("/img", StaticFiles(directory=str(config.STATIC_DIR / "img")), name="img")

_state: dict = {"retriever": None, "count": 0}

# 配额：10 次走模型 + 20 次只摘原文。
# 主键 = 学号 + 设备（两者取用得最多的那个）；IP 只作为高频滥用的兜底闸门，不参与 10 条额度。
# 为什么 IP 不能当主键：校园 WiFi / 隧道后面几十个人可能共用一个出口 IP。
ASK_LIMIT = int(os.environ.get("ASK_LIMIT_PER_HOUR", "10"))
BASIC_LIMIT = int(os.environ.get("ASK_BASIC_LIMIT_PER_HOUR", "20"))
IP_LIMIT = int(os.environ.get("ASK_IP_LIMIT_PER_HOUR", "60"))     # 单 IP 每小时总闸门
SID_RE = re.compile(r"^[a-z]{2}\d{5}$")
_buckets: dict[str, dict] = {}


def norm_sid(raw: str | None) -> str:
    """学号统一小写；格式不对或占位学号返回空串（当匿名）。"""
    s = (raw or "").strip().lower()
    if s in ("uc000000", "uc00000"):      # 默认占位，不能当成一个真实用户
        return ""
    return s if SID_RE.match(s) else ""


def _client_ip(request: Request) -> str:
    return (request.headers.get("cf-connecting-ip")
            or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
            or (request.client.host if request.client else "?"))


def _prune(key: str) -> dict:
    now = time.time()
    b = _buckets.setdefault(key, {"llm": deque(), "basic": deque()})
    for name in ("llm", "basic"):
        dq = b[name]
        while dq and now - dq[0] > 3600:
            dq.popleft()
    return b


def _quota_keys(request: Request, user) -> tuple[list[str], str]:
    """返回 (主键列表, ip)。没有学号也没有设备号时，退回按 IP 计。"""
    ip = _client_ip(request)
    keys = []
    sid = norm_sid(getattr(user, "student_id", ""))
    if sid:
        keys.append("sid:" + sid)
    dev = (request.headers.get("x-device-id") or "").strip()[:64]
    if dev:
        keys.append("dev:" + dev)
    if not keys:
        keys.append("ip:" + ip)
    return keys, ip


def _tier(keys: list[str], ip: str) -> str:
    used_llm = max((len(_prune(k)["llm"]) for k in keys), default=0)
    used_basic = max((len(_prune(k)["basic"]) for k in keys), default=0)
    ip_bucket = _prune("ip:" + ip)
    ip_total = len(ip_bucket["llm"]) + len(ip_bucket["basic"])
    if ip_total >= IP_LIMIT:          # 同出口 IP 刷太狠，先停
        return "none"
    if used_llm < ASK_LIMIT:
        return "llm"
    if used_basic < BASIC_LIMIT:
        return "basic"
    return "none"


def _record(keys: list[str], tier: str, ip: str) -> None:
    now = time.time()
    for k in keys:
        _prune(k)[tier].append(now)
    if "ip:" + ip not in keys:        # IP 桶只做总闸门计数
        _prune("ip:" + ip)["llm" if tier == "llm" else "basic"].append(now)


def _quota(keys: list[str]) -> tuple[int, int]:
    llm_used = max((len(_prune(k)["llm"]) for k in keys), default=0)
    basic_used = max((len(_prune(k)["basic"]) for k in keys), default=0)
    return max(0, ASK_LIMIT - llm_used), max(0, BASIC_LIMIT - basic_used)


def reload_kb() -> int:
    """重建检索索引。审批通过后必须调用，否则新条目查不到。"""
    items = db.published_items()
    _state["retriever"] = Retriever(items)
    _state["count"] = len(items)
    print(f"[reload] 已加载 {len(items)} 条已发布知识")
    return len(items)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    reload_kb()
    set_reload(reload_kb)


class AskIn(BaseModel):
    question: str
    top_k: int = 3


class FeedbackIn(BaseModel):
    question: str
    answer: str = ""
    vote: int                      # 1 有用 / -1 没用
    note: str = ""
    mode: str = ""


@app.post("/api/feedback")
def feedback(body: FeedbackIn, user: User = Depends(get_current_user)) -> dict:
    if body.vote not in (1, -1):
        raise HTTPException(400, "vote 只能是 1 或 -1")
    db.add_feedback(user.student_id, body.question[:300], body.answer[:2000],
                    body.vote, body.note[:500], body.mode)
    return {"ok": True}


@app.get("/health")
def health() -> dict:
    return {"ok": True,
            "model": "llm" if (config.LLM_BASE and config.LLM_KEY) else "extractive",
            "limits": {"llm_per_hour": ASK_LIMIT, "basic_per_hour": BASIC_LIMIT}}


@app.get("/api/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return {"student_id": user.student_id, "name": user.name, "source": user.source}


@app.get("/api/stats")
def stats() -> dict:
    s = db.stats()
    s["loaded_for_search"] = _state["count"]
    return s


@app.post("/api/ask")
def ask(body: AskIn, request: Request, user: User = Depends(get_current_user)) -> dict:
    q = (body.question or "").strip()
    if not q:
        return {"error": "question 不能为空"}
    if len(q) > 300:
        q = q[:300]

    keys, ip = _quota_keys(request, user)

    # 寒暄/客套不调模型，也不该吃掉额度
    if answer_mod.is_smalltalk(q):
        res = answer_mod.answer(q, [])
        db.log_qa(user.student_id, q, res["text"], 0.0)
        return {"answer": res["text"], "mode": res["mode"], "citations": [],
                "user": user.student_id,
                "quota": dict(zip(("llm_left", "basic_left"), _quota(keys)))}

    tier = _tier(keys, ip)
    if tier == "none":
        raise HTTPException(429, f"这个小时已经用完（{ASK_LIMIT} 次 AI 回答 + {BASIC_LIMIT} 次资料摘录）。"
                                 "过一会儿再来，或直接联系书院办公室 8822 9520。")
    _record(keys, tier, ip)
    limit_notice = ""
    if tier == "basic":
        limit_notice = ("（本小时的 AI 回答次数已用完，下面改为直接从书院资料里摘录原文，"
                        "不再调用模型，所以可能不够完整。）\n\n")

    hits = _state["retriever"].search(q, k=body.top_k)
    result = answer_mod.answer(q, hits, allow_llm=(tier == "llm"))
    result["text"] = limit_notice + result["text"]
    db.log_qa(user.student_id, q, result["text"], hits[0]["score"] if hits else 0.0)

    # 书院介绍这类由条目直接拼出来的回答：引用就是那几条，标记已经对齐，不再重编号
    if result.get("sources"):
        cites = result["sources"]
        return {
            "answer": result["text"],
            "mode": result["mode"],
            "citations": cites,
            "user": user.student_id,
            "quota": dict(zip(("llm_left", "basic_left"), _quota(keys))),
        }

    # 只展示模型真正用到的条目，避免「答案说 A、引用写 B」
    all_cites = answer_mod.citations(hits) if hits else []
    used = sorted({i for i in (result.get("used") or []) if 0 < i <= len(all_cites)})
    cites = [all_cites[i - 1] for i in used]

    # 基础档案（楼栋、成立年份、地址电话这类）不挂"依据"卡片：
    # 这些是书院自己的身份信息，学生不需要看条款，来源仍留在库里可查
    if cites and all(c.get("category") == "书院基础档案" for c in cites):
        cites = []

    # 正文里的 [n] 是检索片段序号，不是卡片序号：模型常写 [3] 而只返回 1 张卡。
    # 这里统一重编号成 1..k，找不到对应卡片的标记直接删掉。
    text = result["text"]
    if cites:
        remap = {old: new for new, old in enumerate(used, start=1)}
        text = re.sub(r"\[(\d+)\]", lambda m: f"[{remap[int(m.group(1))]}]" if int(m.group(1)) in remap else "", text)
    else:
        text = re.sub(r"\s*\[\d+\]", "", text)

    return {
        "answer": text,
        "mode": result["mode"],
        "citations": cites,
        "user": user.student_id,
        "quota": dict(zip(("llm_left", "basic_left"), _quota(keys))),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(config.STATIC_DIR) / "index.html")
