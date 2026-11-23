"""内容版本契约：API 输出是否带 uid / revision / content_hash，改动是否真的升版。

    ./.venv/Scripts/python.exe tests/test_versions.py
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = os.environ.get("BASE", "http://127.0.0.1:8001").rstrip("/")
ROOT = Path(__file__).resolve().parent.parent
PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}  {detail}")


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())


def post(path, body, headers=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def main():
    # 1) 单条问答带契约字段
    d = get("/api/qa/9")["item"]
    check("单条带 uid", bool(d.get("uid")), str(d.get("uid")))
    check("uid 形如 kb-0009", str(d.get("uid", "")).startswith("kb-"), str(d.get("uid")))
    check("带 revision", int(d.get("revision") or 0) >= 1, str(d.get("revision")))
    check("带 content_hash（12 位）", len(str(d.get("content_hash") or "")) == 12, str(d.get("content_hash")))

    # 2) 回答引用带版本
    a = post("/api/ask", {"question": "書院能不能養寵物"}, {"X-Student-Id": "uc88888"})
    cites = a.get("citations") or []
    check("回答有引用", bool(cites), str(len(cites)))
    if cites:
        c = cites[0]
        check("引用带 uid", str(c.get("uid", "")).startswith("kb-"), str(c.get("uid")))
        check("引用带 revision", int(c.get("revision") or 0) >= 1, str(c.get("revision")))
        check("引用带 content_hash", len(str(c.get("content_hash") or "")) == 12, str(c.get("content_hash")))

    # 3) 改动才会升版（在临时副本上做，不碰线上库）
    tmp = Path(tempfile.mkdtemp(prefix="ver_"))
    shutil.copy2(ROOT / "data" / "kb.sqlite3", tmp / "kb.sqlite3")
    os.environ["DATA_DIR"] = str(tmp)
    for mod in [m for m in list(sys.modules) if m.startswith("app.")]:
        del sys.modules[mod]
    from app import db  # noqa: E402

    db.init_db()
    before = db.get_item(9)
    db.update_item(9, {"answer": (before["answer"] or "") + "（测试改动）"})
    after = db.get_item(9)
    check("内容变了 revision +1", int(after["revision"]) == int(before["revision"]) + 1,
          f"{before['revision']} → {after['revision']}")
    check("hash 跟着变", after["content_hash"] != before["content_hash"],
          f"{before['content_hash']} → {after['content_hash']}")
    with db.connect() as conn:
        hist = conn.execute("SELECT COUNT(*) FROM kb_revision WHERE uid=?", (after["uid"],)).fetchone()[0]
    check("历史表留了旧版", hist >= 1, str(hist))

    db.update_item(9, {"note": "只改备注，不该升版"})
    same = db.get_item(9)
    check("只改备注不升版", int(same["revision"]) == int(after["revision"]),
          f"{after['revision']} → {same['revision']}")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
