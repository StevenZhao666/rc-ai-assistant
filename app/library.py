"""资料库的公开接口与页面（只读）。

/api/library        列表：?kind=work|link|doc&q=关键词
/api/library/{id}   单条
/api/search         统一检索（问答 + 资料库）
/library            浏览页
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from . import config, db

router = APIRouter()


@router.get("/api/library")
def library_list(kind: str = "", q: str = "", limit: int = Query(100, ge=1, le=300)) -> dict:
    items = db.library_items(kind=kind, q=q, limit=limit)
    counts = {k: len(db.library_items(kind=k, limit=500)) for k in ("work", "link", "doc")}
    return {"items": items, "counts": counts, "total": sum(counts.values())}


@router.get("/api/library/{item_id}")
def library_one(item_id: int) -> dict:
    it = db.library_item(item_id)
    if not it or it.get("status") != "published":
        raise HTTPException(404, "没有这一条")
    return {"item": it}


@router.get("/api/search")
def search(q: str = "", limit: int = Query(20, ge=1, le=50)) -> dict:
    return {"q": q, "items": db.search_all(q, limit=limit)}


@router.get("/api/qa/{item_id}")
def qa_one(item_id: int) -> dict:
    with db.connect() as conn:
        conn.row_factory = __import__("sqlite3").Row
        r = conn.execute(
            "SELECT id, uid, revision, content_hash, effective_from, question, answer, category,"
            " source, source_url, ttl_type, verified_at"
            " FROM kb_item WHERE id=? AND status='published'", (item_id,)).fetchone()
    if not r:
        raise HTTPException(404, "没有这一条")
    return {"item": dict(r)}


@router.get("/api/clause")
def clause(anchor: str = "", version: str = "") -> dict:
    """按条款号取原文（同号多章节时全部返回，前端/客户端自己选）。"""
    if not anchor:
        raise HTTPException(400, "需要 anchor，例如 3.2")
    rows = db.get_clauses(anchor.strip(), version.strip())
    if not rows:
        raise HTTPException(404, f"没有第 {anchor} 条")
    return {"anchor": anchor, "versions": rows}


@router.get("/api/updates")
def updates(since: str = "", limit: int = 100) -> dict:
    """自某日起新增或更新的内容：问答 + 资料库。"""
    import sqlite3
    from datetime import date
    since = since.strip() or "1970-01-01"
    out = {"since": since, "qa": [], "library": []}
    with db.connect() as conn:
        conn.row_factory = sqlite3.Row
        out["qa"] = [dict(r) for r in conn.execute(
            "SELECT id, question, status, COALESCE(verified_at, created_at) AS updated_at FROM kb_item"
            " WHERE status='published' AND COALESCE(verified_at, created_at, '') >= ?"
            " ORDER BY updated_at DESC LIMIT ?",
            (since, limit)).fetchall()]
        out["library"] = [dict(r) for r in conn.execute(
            "SELECT id, kind, title, reviewed_at FROM library_item"
            " WHERE status='published' AND COALESCE(reviewed_at,'') >= ? ORDER BY reviewed_at DESC LIMIT ?",
            (since, limit)).fetchall()]
    return out


@router.get("/library")
def library_page() -> FileResponse:
    return FileResponse(Path(config.STATIC_DIR) / "library.html")
