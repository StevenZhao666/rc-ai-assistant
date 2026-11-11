"""审批后台：给几个人分工批改知识库。

三条链路：
1. 待审队列：按分类/状态筛选 → 认领（锁 30 分钟）→ 通过 / 退回 / 改后通过 / 归档
2. 新资料：贴官网链接 → 抓正文存成候选 → 写成问答条目 → 进待审
3. 缺口清单：学生问了但答不上来的问题，按次数排序 → 去官网找答案

身份：请求头 X-Reviewer（学号或姓名）。上线后由 PHP 认证填充，前端不再自己填。
并发：每条带 version，保存时校验；对不上就报冲突，不覆盖别人刚改的内容。
"""
import re
import urllib.request
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import config, db

router = APIRouter()

# 由 main 注入：审批通过后要重建检索索引，否则新条目查不到
_reload_hook = None


def set_reload(fn) -> None:
    global _reload_hook
    _reload_hook = fn


def _reviewer(request: Request) -> str:
    who = (request.headers.get("X-Reviewer") or "").strip()
    if not who:
        raise HTTPException(401, "缺少审核人身份：请在页面顶部填学号，或由网关注入 X-Reviewer")
    allowed = config.REVIEWERS
    if allowed and who not in allowed:
        raise HTTPException(403, f"{who} 不在审核人名单里")
    return who


def _reload() -> None:
    if _reload_hook:
        try:
            _reload_hook()
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 重建检索索引失败：{e}")


class DecideIn(BaseModel):
    action: str                 # approve / reject / edit / archive
    note: str = ""
    patch: dict = {}
    version: int | None = None


class BulkIn(BaseModel):
    ids: list[int]
    action: str
    note: str = ""


class ScanIn(BaseModel):
    url: str


class DraftIn(BaseModel):
    question: str
    answer: str
    category: str = "未分类"
    ttl_type: str = "A"
    source: str = ""
    source_url: str = ""


@router.get("/review")
def review_page() -> FileResponse:
    return FileResponse(Path(config.STATIC_DIR) / "review.html")


@router.get("/api/review/queue")
def queue(request: Request, status: str = "", q: str = "", category: str = "") -> dict:
    _reviewer(request)
    items = db.list_items(status or None, q)
    if category:
        items = [i for i in items if (i.get("category") or "") == category]
    return {"items": items, "count": len(items)}


@router.get("/api/review/item/{item_id}")
def item(item_id: int, request: Request) -> dict:
    _reviewer(request)
    it = db.get_item(item_id)
    if not it:
        raise HTTPException(404, "条目不存在")
    return {"item": it, "history": db.item_history(item_id)}


@router.post("/api/review/item/{item_id}/claim")
def claim(item_id: int, request: Request) -> dict:
    who = _reviewer(request)
    ok, it = db.claim_item(item_id, who)
    if not ok:
        raise HTTPException(409, f"这条已被 {it.get('owner')} 认领，请稍后或换一条")
    return {"ok": True, "item": it}


@router.post("/api/review/item/{item_id}/release")
def release(item_id: int, request: Request) -> dict:
    db.release_item(item_id, _reviewer(request))
    return {"ok": True}


@router.post("/api/review/item/{item_id}/decide")
def decide(item_id: int, body: DecideIn, request: Request) -> dict:
    who = _reviewer(request)
    ok, reason, it = db.decide_item(item_id, body.action, who, body.note,
                                    body.patch, body.version)
    if not ok:
        if reason == "conflict":
            raise HTTPException(409, f"这条已被别人改过（现在是 v{it.get('version')}），请刷新后再看")
        if reason == "not_found":
            raise HTTPException(404, "条目不存在")
        raise HTTPException(400, f"不支持的动作：{body.action}")
    if body.action in ("approve", "edit", "reject", "archive"):
        _reload()
    return {"ok": True, "item": it, "reloaded": True}


@router.post("/api/review/bulk")
def bulk(body: BulkIn, request: Request) -> dict:
    who = _reviewer(request)
    done, skipped = [], []
    for i in body.ids:
        ok, reason, _ = db.decide_item(i, body.action, who, body.note)
        (done if ok else skipped).append(i)
    _reload()
    return {"ok": True, "done": done, "skipped": skipped}


@router.get("/api/review/stats")
def stats(request: Request) -> dict:
    _reviewer(request)
    s = db.review_stats()
    s["recent"] = db.recent_log(15)
    s["gaps"] = db.unanswered(13)
    return s


@router.post("/api/review/scan")
def scan(body: ScanIn, request: Request) -> dict:
    """贴一个官网链接，抓正文存成候选。只负责取原文，不自动生成答案。"""
    _reviewer(request)
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "请填完整链接（http/https 开头）")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"抓取失败：{type(e).__name__}: {e}")

    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]
    body_html = re.sub(r"(?is)<(script|style|nav|footer|header|noscript)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", "\n", body_html)
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) < 40:
        raise HTTPException(422, "页面上没抽到正文（可能是纯 JS 渲染），换个页面或用「手工录入」")

    cid = db.add_candidate(url, title or url, text[:12000])
    return {"ok": True, "candidate_id": cid, "chars": len(text), "title": title}


@router.get("/api/review/candidates")
def candidates(request: Request, status: str = "new") -> dict:
    _reviewer(request)
    return {"items": db.list_candidates(status or None)}


@router.post("/api/review/candidates/{cid}/draft")
def candidate_to_draft(cid: int, body: DraftIn, request: Request) -> dict:
    """把候选原文提炼成一问一答，进待审队列（不直接发布）。"""
    who = _reviewer(request)
    c = db.get_candidate(cid)
    if not c:
        raise HTTPException(404, "候选不存在")
    if not body.question.strip() or not body.answer.strip():
        raise HTTPException(400, "问题和答案都要填")
    new_id = db.create_item({
        "question": body.question.strip(),
        "answer": body.answer.strip(),
        "category": body.category,
        "ttl_type": body.ttl_type,
        "source": body.source or c.get("title") or "官网",
        "source_url": body.source_url or c.get("url"),
        "source_type": "official",
        "status": "review",
        "owner": who,
        "reviewer": "",
        "created_at": date.today().isoformat(),
    })
    db.decide_candidate(cid, "accepted", who, note=f"生成条目 #{new_id}", item_id=new_id)
    db.log_review(new_id, "create", who, f"来自候选 #{cid}", after={"question": body.question})
    return {"ok": True, "item_id": new_id}


@router.post("/api/review/candidates/{cid}/reject")
def candidate_reject(cid: int, request: Request, note: str = "") -> dict:
    who = _reviewer(request)
    if not db.get_candidate(cid):
        raise HTTPException(404, "候选不存在")
    db.decide_candidate(cid, "rejected", who, note=note)
    return {"ok": True}


@router.get("/api/review/gaps")
def gaps(request: Request) -> dict:
    _reviewer(request)
    return {"unanswered": db.unanswered(50), "bad": db.bad_feedback(20)}


@router.get("/api/review/categories")
def categories(request: Request) -> dict:
    _reviewer(request)
    cats = {}
    for it in db.list_items():
        c = it.get("category") or "未分类"
        cats[c] = cats.get(c, 0) + 1
    return {"categories": [{"name": k, "n": v} for k, v in sorted(cats.items(), key=lambda x: -x[1])]}
