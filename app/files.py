"""文件检索：只暴露已上架条目里的文件。

- GET /api/files?q=&kind=&limit   搜文件名 / 所属条目标题说明
- GET /api/files/{id}             单个文件
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from . import config, db

router = APIRouter()


def _published_files() -> list[dict]:
    """已发布条目 → 文件列表。文件没挂到已发布条目上的，一律不给。"""
    out: list[dict] = []
    with db.connect() as conn:
        conn.row_factory = sqlite3.Row
        items = [dict(r) for r in conn.execute(
            "SELECT id, kind, title, author, note, file_ids FROM library_item WHERE status='published'"
        ).fetchall()]
        files = {r["id"]: dict(r) for r in conn.execute(
            "SELECT id, path, orig_name, mime, size_bytes FROM upload_file").fetchall()}
    for it in items:
        for fid in json.loads(it.get("file_ids") or "[]"):
            f = files.get(fid)
            if not f:
                continue
            out.append({
                "file_id": f["id"],
                "name": f["orig_name"],
                "mime": f["mime"],
                "size_bytes": f["size_bytes"],
                "url": "/files/" + str(f["path"]).replace("\\", "/").split("files/", 1)[-1],
                "item_id": it["id"],
                "kind": it["kind"],
                "title": it["title"],
                "author": it["author"],
                "note": it["note"],
            })
    return out


@router.get("/api/files")
def files_list(q: str = "", kind: str = "", limit: int = Query(50, ge=1, le=200)) -> dict:
    rows = _published_files()
    if kind:
        rows = [r for r in rows if r["kind"] == kind]
    if q:
        grams = db._tokens(q)
        rows = [r for r in rows if db._score(f"{r['name']} {r['title']} {r['note']}", grams) > 0]
    return {"total": len(rows), "items": rows[:limit]}


@router.get("/api/files/{file_id}")
def files_one(file_id: int) -> dict:
    for r in _published_files():
        if r["file_id"] == file_id:
            return {"item": r}
    raise HTTPException(404, "没有这个文件")


@router.get("/files-download/{file_id}")
def files_download(file_id: int) -> FileResponse:
    for r in _published_files():
        if r["file_id"] == file_id:
            p = Path(config.FILES_DIR) / r["url"].split("/files/", 1)[-1]
            if p.exists():
                return FileResponse(p, filename=r["name"])
    raise HTTPException(404, "没有这个文件")
