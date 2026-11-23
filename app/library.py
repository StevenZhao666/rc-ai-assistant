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


@router.get("/library")
def library_page() -> FileResponse:
    return FileResponse(Path(config.STATIC_DIR) / "library.html")
