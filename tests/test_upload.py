"""投稿上传的专项测试（不需要额外依赖）。

    ./.venv/Scripts/python.exe tests/test_upload.py

覆盖：邀请码、授权声明、类型白名单、超限、去重、限流、候选入库。
每个用例用不同的 X-Forwarded-For，互不影响限流计数。
"""
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path

import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get("BASE", "http://127.0.0.1:8001").rstrip("/")
CODE = os.environ.get("UPLOAD_CODE", "cklc-test-2026")

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}  {detail}")


def multipart(fields: dict, files: list[tuple[str, str, bytes]]):
    boundary = "----b" + uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for name, filename, data in files:
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
                f"filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
        out += data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def post(fields, files, ip):
    body, ctype = multipart(fields, files)
    req = urllib.request.Request(BASE + "/api/upload", data=body, method="POST",
                                 headers={"Content-Type": ctype, "X-Forwarded-For": ip})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def ip():
    return f"10.0.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"


def ok_fields(**kw):
    base = {"code": CODE, "kind": "work", "title": "測試作品", "author": "測試",
            "contact": "", "note": "說明", "consent": "1"}
    base.update(kw)
    return base


def main():
    code, info = json.load(urllib.request.urlopen(BASE + "/api/upload/info", timeout=20)), None
    check("投稿接口已开启", code.get("open") is True, str(code))

    code, d = post(ok_fields(code="wrong"), [("files", "a.pdf", b"%PDF-1.4 test")], ip())
    check("邀请码错被拒 403", code == 403, f"{code} {d}")

    code, d = post(ok_fields(consent=""), [("files", "a.pdf", b"%PDF-1.4 test")], ip())
    check("没勾授权被拒 400", code == 400, f"{code} {d}")

    code, d = post(ok_fields(), [("files", "bad.exe", b"MZ\x90\x00")], ip())
    check("exe 被拒 415", code == 415, f"{code} {d}")

    fake_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"
    code, d = post(ok_fields(title="上傳測試 PDF"), [("files", "demo.pdf", fake_pdf)], ip())
    check("正常 PDF 能上传", code == 200 and d.get("ok"), f"{code} {d}")
    cand_id = d.get("id")
    url = (d.get("files") or [{}])[0].get("url", "")
    check("返回候选编号", isinstance(cand_id, int) and cand_id > 0, str(cand_id))
    check("返回文件地址", url.startswith("/files/"), url)

    # 候选确实入库
    with sqlite3.connect(ROOT / "data" / "kb.sqlite3") as conn:
        row = conn.execute("SELECT title, kind, status FROM candidate WHERE id=?", (cand_id,)).fetchone()
    check("候选表里有这条（pending）", row and row[2] == "pending", str(row))

    # 去重：同一个文件再传，sha 与地址一致
    code2, d2 = post(ok_fields(title="上傳測試 PDF 2"), [("files", "demo2.pdf", fake_pdf)], ip())
    f1 = (d.get("files") or [{}])[0]
    f2 = (d2.get("files") or [{}])[0]
    check("同内容文件不重复存", code2 == 200 and f1.get("sha256") == f2.get("sha256"), f"{f1} vs {f2}")
    check("同内容复用同一路径", f1.get("url") == f2.get("url"), f"{f1.get('url')} vs {f2.get('url')}")

    # 超限：21 MB
    big = b"%PDF-1.4\n" + b"0" * (21 * 1024 * 1024)
    code, d = post(ok_fields(title="太大"), [("files", "big.pdf", big)], ip())
    check("超过 20MB 被拒 413", code == 413, f"{code} {d}")

    # 限流：同一个 IP 连续提交 6 次
    same = ip()
    codes = [post(ok_fields(title=f"限流 {i}"), [("files", f"x{i}.md", b"# hi")], same)[0] for i in range(6)]
    check("同一 IP 第 6 次被限流", codes[:5].count(200) == 5 and codes[5] == 429, str(codes))

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
