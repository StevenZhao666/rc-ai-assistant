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
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import answer as answer_mod
from . import config, db
from .auth import User, get_current_user
from .retrieve import Retriever
from .admin import router as admin_router
from .files import router as files_router
from .library import router as library_router
from .upload import router as upload_router
from .review import router as review_router
from .review import set_reload

app = FastAPI(title="RC AI Assistant", version="0.2.0")
app.include_router(review_router)
app.include_router(admin_router)
app.include_router(upload_router)
app.include_router(library_router)
app.include_router(files_router)
app.mount("/img", StaticFiles(directory=str(config.STATIC_DIR / "img")), name="img")
config.FILES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(config.FILES_DIR)), name="files")


# ── 反扒：令牌桶限速（按 IP，分路径）+ 下载限速 + 安全头 ─────────────────────
PUBLIC_PATHS = ("/api/library", "/api/search", "/api/files", "/api/qa/", "/api/clause",
                "/api/updates", "/files/")
SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT_PER_MIN", "60"))   # 每分钟补充的令牌数
SCRAPE_BURST = int(os.environ.get("SCRAPE_BURST", "20"))           # 一次最多攒这么多
SCRAPE_BYPASS = os.environ.get("SCRAPE_BYPASS", "")                # 内部脚本用，别对外说
_buckets: dict[str, list] = {}          # ip -> [tokens, last_ts]


def _client_ip(request: Request) -> str:
    # 取最后一跳（我们自己的 Apache 追加的），防止客户端伪造 XFF 绕过限速
    xff = request.headers.get("x-forwarded-for") or ""
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    return (parts[-1] if parts else (request.client.host if request.client else "?"))


def _take(ip: str, now: float, cost: float = 1.0) -> bool:
    """令牌桶：平时按 SCRAPE_LIMIT/60 每秒补，最多攒 SCRAPE_BURST 个。"""
    b = _buckets.get(ip)
    if b is None:
        b = [float(SCRAPE_BURST), now]
        _buckets[ip] = b
    tokens = min(float(SCRAPE_BURST), b[0] + (now - b[1]) * (SCRAPE_LIMIT / 60.0))
    if tokens < cost:
        b[0], b[1] = tokens, now
        return False
    b[0], b[1] = tokens - cost, now
    return True


@app.middleware("http")
async def scrape_guard(request: Request, call_next):
    path = request.url.path
    guarded = any(path.startswith(p) for p in PUBLIC_PATHS)
    if guarded and SCRAPE_BYPASS and request.headers.get("x-scrape-token") == SCRAPE_BYPASS:
        guarded = False                     # 内部评测脚本放行
    if guarded:
        now = time.time()
        # 搜索更贵：一次算 3 个令牌，避免有人拿它当全库扫描器
        cost = 3.0 if path.startswith("/api/search") else 1.0
        if not _take(_client_ip(request), now, cost):
            return JSONResponse({"detail": "请求太频繁，请一分钟后再试"}, status_code=429,
                                headers={"Retry-After": "30", "X-Robots-Tag": "noindex",
                                         "Cache-Control": "no-store"})
        if len(_buckets) > 5000:                       # 防止字典无限长
            for k in [k for k, v in _buckets.items() if v[0] >= SCRAPE_BURST][:1000]:
                _buckets.pop(k, None)

    resp = await call_next(request)

    resp.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    if request.method == "GET" and guarded:
        resp.headers.setdefault("Cache-Control", "public, max-age=60")
    # 用户上传的 svg/html 不当作页面执行
    low = path.lower()
    if low.startswith("/files/") and low.endswith((".svg", ".html", ".htm")):
        resp.headers["Content-Disposition"] = "attachment"
        resp.headers["Content-Security-Policy"] = "sandbox"
    return resp


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
    session_id = (request.headers.get("X-Session-Id") or request.headers.get("X-Device-Id") or "")[:64]
    t0 = time.perf_counter()

    tier = _tier(keys, ip)
    if tier == "none":
        raise HTTPException(429, f"这个小时已经用完（{ASK_LIMIT} 次 AI 回答 + {BASIC_LIMIT} 次资料摘录）。"
                                 "过一会儿再来，或直接联系书院办公室 8822 9520。")
    limit_notice = ""
    if tier == "basic":
        limit_notice = ("（本小时的 AI 回答次数已用完，下面改为直接从书院资料里摘录原文，"
                        "不再调用模型，所以可能不够完整。）\n\n")

    hits = _state["retriever"].search(q, k=body.top_k)
    result = answer_mod.answer(q, hits, allow_llm=(tier == "llm"))
    # 闲聊（chat）不占额度；其余正常记账
    if result.get("mode") != "chat":
        _record(keys, tier, ip)
    result["text"] = limit_notice + result["text"]

    # 书院介绍这类由条目直接拼出来的回答：引用就是那几条，标记已经对齐，不再重编号
    if result.get("sources"):
        out = {
            "answer": result["text"],
            "mode": result["mode"],
            "citations": result["sources"],
            "user": user.student_id,
            "quota": dict(zip(("llm_left", "basic_left"), _quota(keys))),
        }
        _log(q, hits, out, t0, session_id)
        return out

    # 只展示模型真正用到的条目，避免「答案说 A、引用写 B」
    all_cites = answer_mod.citations(hits) if hits else []
    used = sorted({i for i in (result.get("used") or []) if 0 < i <= len(all_cites)})
    # 可追溯性兜底：模型偶尔忘了标 [n]，但检索确实命中时，仍把最相关的那条挂出来
    if (not used and result.get("mode", "").startswith("llm")
            and hits and hits[0].get("score", 0) >= config.MIN_SCORE):
        used = [1]
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

    out = {
        "answer": text,
        "mode": result["mode"],
        "citations": cites,
        "user": user.student_id,
        "quota": dict(zip(("llm_left", "basic_left"), _quota(keys))),
    }
    _log(q, hits, out, t0, session_id)
    return out


def _log(q: str, hits: list, out: dict, t0: float, session_id: str) -> None:
    """写提问流水：带模式、耗时、会话、引用数，后台看板全靠这几个字段。"""
    db.log_qa(
        out.get("user") or "",
        q,
        out.get("answer") or "",
        hits[0]["score"] if hits else 0.0,
        mode=out.get("mode") or "",
        latency_ms=int((time.perf_counter() - t0) * 1000),
        session_id=session_id,
        n_cites=len(out.get("citations") or []),
    )


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(Path(config.STATIC_DIR) / "admin.html")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(config.STATIC_DIR) / "index.html")
