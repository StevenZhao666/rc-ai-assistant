"""投稿上传：/upload 页面 + POST /api/upload。

设计要点：
- 上传只进候选（candidate），不能直接发布
- 文件只存路径与指纹，不存二进制；同哈希复用，不重复占空间
- 白名单 + 大小上限 + 每 IP 限流；邀请码留空 = 关闭投稿
"""
from __future__ import annotations

import hashlib
import re
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from . import config, db

router = APIRouter()

EXT_MIME = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".md": "text/markdown",
    ".zip": "application/zip",
}
MAGIC = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".webp": (b"RIFF",),
    ".zip": (b"PK\x03\x04",),
}

# 每 IP 的投稿频率（内存计数，进程重启即清零；够用）
_HITS: dict[str, deque] = defaultdict(deque)
HOUR, DAY = 3600, 86400


def _ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For") or ""
    return (fwd.split(",")[0].strip() or request.client.host or "?")


def _allow(ip: str) -> bool:
    now = time.time()
    q = _HITS[ip]
    while q and now - q[0] > DAY:
        q.popleft()
    last_hour = sum(1 for t in q if now - t <= HOUR)
    if last_hour >= 5 or len(q) >= 20:
        return False
    q.append(now)
    return True


def _save(f: UploadFile) -> dict:
    name = Path(f.filename or "file").name
    ext = Path(name).suffix.lower()
    if ext not in EXT_MIME:
        raise HTTPException(415, f"不接受这种文件类型：{ext or '无扩展名'}（只收 {', '.join(EXT_MIME)}）")

    limit = config.UPLOAD_MAX_MB * 1024 * 1024
    h = hashlib.sha256()
    size = 0
    head = b""
    tmp = config.FILES_DIR / "inbox" / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp / f"{time.time_ns()}{ext}"
    with tmp_path.open("wb") as out:
        while True:
            chunk = f.file.read(1024 * 256)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                out.close()
                tmp_path.unlink(missing_ok=True)
                raise HTTPException(413, f"文件太大（上限 {config.UPLOAD_MAX_MB} MB）")
            if len(head) < 16:
                head += chunk[: 16 - len(head)]
            h.update(chunk)
            out.write(chunk)

    if size == 0:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(400, "空文件")

    magic = MAGIC.get(ext)
    if magic and not any(head.startswith(m) for m in magic):
        # webp 的 RIFF 后面要跟 WEBP
        if not (ext == ".webp" and head[8:12] == b"WEBP"):
            tmp_path.unlink(missing_ok=True)
            raise HTTPException(415, "文件内容和扩展名对不上，已拒绝")

    sha = h.hexdigest()
    month = datetime.now().strftime("%Y%m")
    dest_dir = config.FILES_DIR / "inbox" / month
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{sha[:12]}{ext}"
    if dest.exists():
        tmp_path.unlink(missing_ok=True)          # 同哈希已有，直接复用
    else:
        tmp_path.replace(dest)

    rel = dest.relative_to(config.DATA_DIR).as_posix()
    file_id = db.add_file(sha, rel, name, EXT_MIME[ext], size)
    return {"file_id": file_id, "name": name, "size": size, "mime": EXT_MIME[ext],
            "sha256": sha, "url": f"/files/{rel}"}


@router.get("/upload")
def upload_page() -> FileResponse:
    return FileResponse(Path(config.STATIC_DIR) / "upload.html")


@router.get("/api/upload/info")
def upload_info() -> dict:
    return {"open": bool(config.UPLOAD_CODE), "max_mb": config.UPLOAD_MAX_MB,
            "max_files": config.UPLOAD_MAX_FILES, "types": list(EXT_MIME)}


@router.post("/api/upload")
async def upload(request: Request,
                 code: str = Form(""),
                 kind: str = Form("work"),
                 title: str = Form(""),
                 author: str = Form(""),
                 contact: str = Form(""),
                 note: str = Form(""),
                 consent: str = Form(""),
                 files: list[UploadFile] = File(default=[])) -> dict:
    if not config.UPLOAD_CODE:
        raise HTTPException(503, "投稿暂未开放")
    if code.strip() != config.UPLOAD_CODE:
        raise HTTPException(403, "邀请码不对")
    if consent not in ("1", "true", "on", "yes"):
        raise HTTPException(400, "需要勾选授权声明")
    title = title.strip()
    if len(title) < 2:
        raise HTTPException(400, "标题太短")
    if kind not in ("work", "link", "doc"):
        raise HTTPException(400, "类型不对")
    contact = (contact or "").strip()
    if not contact:
        raise HTTPException(400, "请填一个电邮地址，审核结果会通知你")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", contact):
        raise HTTPException(400, "电邮格式不对")
    files = [f for f in files if f and f.filename]
    if not files:
        raise HTTPException(400, "至少传一个文件")
    if len(files) > config.UPLOAD_MAX_FILES:
        raise HTTPException(400, f"最多 {config.UPLOAD_MAX_FILES} 个文件")

    ip = _ip(request)
    if not _allow(ip):
        raise HTTPException(429, "提交太频繁，请一小时后再试")

    saved = [_save(f) for f in files]
    cand_id = db.add_upload_candidate(
        title=title, kind=kind, author=author.strip(), contact=contact.strip(),
        note=note.strip(), file_ids=[s["file_id"] for s in saved], ip=ip)

    try:
        with (config.DATA_DIR / "upload.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now().isoformat(timespec='seconds')}\t#{cand_id}\t{kind}\t{title}\t"
                     f"{author}\t{len(saved)} 个文件\t{ip}\n")
    except Exception:
        pass

    return {"ok": True, "id": cand_id, "files": saved}
