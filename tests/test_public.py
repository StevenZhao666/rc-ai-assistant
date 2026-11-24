"""资料库公开接口测试：列表、筛选、单条、统一检索、隐私。

    ./.venv/Scripts/python.exe tests/test_public.py
"""
import json
import os
import sys
import uuid
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("BASE", "http://127.0.0.1:8001").rstrip("/")
CODE = os.environ.get("UPLOAD_CODE", "cklc-test-2026")
REV = os.environ.get("TEST_REVIEWER", "uc99999")

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}  {detail}")


def call(path, method="GET", body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw.decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def upload(title, kind="work", contact_public="1", note="說明"):
    boundary = "----b" + uuid.uuid4().hex
    fields = {"code": CODE, "kind": kind, "title": title, "author": "公開測試",
              "contact": "pub@example.com", "note": note, "consent": "1",
              "contact_public": contact_public}
    data = b""
    for k, v in fields.items():
        data += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    data += (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="x.md"\r\n'
             f"Content-Type: text/markdown\r\n\r\n# hello\r\n").encode()
    data += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + "/api/upload", data=data, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                                          "X-Forwarded-For": f"10.8.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def approve(cid):
    return call(f"/api/review/uploads/{cid}/decide", "POST",
                {"action": "approve", "note": ""}, {"X-Reviewer": REV})


def _cleanup(reviewer="uc99999"):
    """把测试造出来的条目下架，避免污染公网资料库。"""
    import json as _json
    import urllib.request as _u
    try:
        lib = _json.loads(_u.urlopen(BASE + "/api/library?limit=200", timeout=20).read())
    except Exception:
        return
    marks = ("審核測試", "公开测试", "公開測試", "私密聯絡", "MCP測試", "限流")
    for it in lib.get("items", []):
        if not str(it.get("title", "")).startswith(marks):
            continue
        try:
            req = _u.Request(f"{BASE}/api/review/library/{it['id']}/archive", data=b"{}", method="POST",
                             headers={"Content-Type": "application/json", "X-Reviewer": reviewer})
            _u.urlopen(req, timeout=20).read()
        except Exception:
            pass

def main():
    a = upload("公開測試作品甲", kind="work")
    b = upload("公開測試網站乙", kind="link")
    c = upload("私密聯絡丙", kind="doc", contact_public="0")
    for x in (a, b, c):
        approve(x["id"])

    code, d = call("/api/library")
    titles = [i["title"] for i in d.get("items", [])]
    check("列表能读到已发布的投稿", code == 200 and "公開測試作品甲" in titles, str(titles[:5]))
    check("列表带计数", isinstance(d.get("counts"), dict) and d["counts"].get("work", 0) >= 1, str(d.get("counts")))

    code, d = call("/api/library?kind=link")
    kinds = {i["kind"] for i in d.get("items", [])}
    check("按类型筛选只有 link", kinds == {"link"}, str(kinds))

    code, d = call("/api/library?q=" + urllib.parse.quote("作品甲"))
    check("按关键词筛选命中", any("作品甲" in i["title"] for i in d.get("items", [])), str([i["title"] for i in d["items"]][:3]))

    item_id = next(i["id"] for i in call("/api/library")[1]["items"] if i["title"] == "公開測試作品甲")
    code, one = call(f"/api/library/{item_id}")
    it = one.get("item", {})
    check("单条可读且带文件", code == 200 and it.get("files"), str(it)[:120])
    check("勾了公开才带邮箱", it.get("contact") == "pub@example.com", str(it.get("contact")))

    cid = next(i["id"] for i in call("/api/library")[1]["items"] if i["title"] == "私密聯絡丙")
    code, one_c = call(f"/api/library/{cid}")
    check("没勾公开的单条不带邮箱", "contact" not in one_c.get("item", {}), str(one_c)[:120])

    code, d = call("/api/library/999999")
    check("不存在的条目 404", code == 404, str(code))

    code, s = call("/api/search?q=" + urllib.parse.quote("換房間"))
    types = {x["type"] for x in s.get("items", [])}
    check("统一检索能返回问答", "qa" in types, str(types))

    code, s2 = call("/api/search?q=" + urllib.parse.quote("公開測試作品甲"))
    types2 = {x["type"] for x in s2.get("items", [])}
    check("统一检索能返回资料库条目", "work" in types2, str(types2))

    code, page = call("/library")
    body = page if isinstance(page, str) else json.dumps(page, ensure_ascii=False)
    check("浏览页可打开", code == 200 and ("書院資料庫" in body or "college" in body.lower()), str(code))

    _cleanup()

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
