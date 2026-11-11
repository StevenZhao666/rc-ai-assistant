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
from pydantic import BaseModel

from . import answer as answer_mod
from . import config, db
from .auth import User, get_current_user
from .retrieve import Retriever
from .review import router as review_router
from .review import set_reload

app = FastAPI(title="RC AI Assistant", version="0.1.0")
app.include_router(review_router)

_state: dict = {"retriever": None, "count": 0}

# 每 IP 每小时配额：前 10 次走模型，接下来 20 次只做资料摘录（不花钱），再往后拒绝。
ASK_LIMIT = int(os.environ.get("ASK_LIMIT_PER_HOUR", "10"))
BASIC_LIMIT = int(os.environ.get("ASK_BASIC_LIMIT_PER_HOUR", "20"))
_buckets: dict[str, dict] = {}


def _quota(key: str) -> tuple[int, int]:
    """返回 (还能用模型的次数, 还能用基础模式的次数)，顺手清理一小时前的记录。"""
    now = time.time()
    b = _buckets.setdefault(key, {"llm": deque(), "basic": deque()})
    for name in ("llm", "basic"):
        dq = b[name]
        while dq and now - dq[0] > 3600:
            dq.popleft()
    return max(0, ASK_LIMIT - len(b["llm"])), max(0, BASIC_LIMIT - len(b["basic"]))


def _allow(key: str) -> str:
    """llm / basic / none"""
    llm_left, basic_left = _quota(key)
    b = _buckets[key]
    if llm_left > 0:
        b["llm"].append(time.time())
        return "llm"
    if basic_left > 0:
        b["basic"].append(time.time())
        return "basic"
    return "none"


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

    # 公网走隧道时，所有请求的 client.host 都是 127.0.0.1——必须看真实来源 IP，
    # 否则全世界的用户共用一个桶，第 11 个人就被降级了。
    ip = (request.headers.get("cf-connecting-ip")
          or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
          or (request.client.host if request.client else "?"))
    tier = _allow(ip)
    if tier == "none":
        raise HTTPException(429, f"这个小时已经用完（{ASK_LIMIT} 次 AI 回答 + {BASIC_LIMIT} 次资料摘录）。"
                                 "过一会儿再来，或直接联系书院办公室 8822 9520。")
    limit_notice = ""
    if tier == "basic":
        limit_notice = ("（本小时的 AI 回答次数已用完，下面改为直接从书院资料里摘录原文，"
                        "不再调用模型，所以可能不够完整。）\n\n")

    hits = _state["retriever"].search(q, k=body.top_k)
    result = answer_mod.answer(q, hits, allow_llm=(tier == "llm"))
    result["text"] = limit_notice + result["text"]
    db.log_qa(user.student_id, q, result["text"], hits[0]["score"] if hits else 0.0)

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
        "quota": dict(zip(("llm_left", "basic_left"), _quota(ip))),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(config.STATIC_DIR) / "index.html")
