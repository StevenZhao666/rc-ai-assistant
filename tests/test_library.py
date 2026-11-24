"""投稿审核（第 2 阶段）测试：候选 → 通过/退回 → 资料库。

    ./.venv/Scripts/python.exe tests/test_library.py
"""
import json
import os
import sys
import uuid
import urllib.error
import urllib.request

BASE = os.environ.get("BASE", "http://127.0.0.1:8001").rstrip("/")
CODE = os.environ.get("UPLOAD_CODE", "cklc-test-2026")
REVIEWER = os.environ.get("TEST_REVIEWER", "uc99999")

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
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def upload(title, author="測試", contact_public="1"):
    boundary = "----b" + uuid.uuid4().hex
    fields = {"code": CODE, "kind": "work", "title": title, "author": author,
              "contact": "tester@example.com", "note": "測試用", "consent": "1",
              "contact_public": contact_public}
    data = b""
    for k, v in fields.items():
        data += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    data += (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="t.md"\r\n'
             f"Content-Type: text/markdown\r\n\r\n# hi\r\n").encode()
    data += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + "/api/upload", data=data, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                                          "X-Forwarded-For": f"10.9.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


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
    a = upload("審核測試 A", contact_public="1")
    b = upload("審核測試 B", contact_public="0")
    check("两条投稿都进来了", a.get("ok") and b.get("ok"), f"{a} {b}")

    code, _ = call("/api/review/uploads")
    check("投稿列表需要审核人", code == 401, str(code))

    code, lst = call("/api/review/uploads", headers={"X-Reviewer": REVIEWER})
    ids = [x["id"] for x in lst.get("items", [])]
    check("列表里能看到投稿", code == 200 and a["id"] in ids and b["id"] in ids, str(ids[:5]))
    first = next((x for x in lst.get("items", []) if x["id"] == a["id"]), {})
    check("投稿带附件信息", bool(first.get("files")), str(first)[:120])

    code, d = call(f"/api/review/uploads/{a['id']}/decide", "POST", {"action": "approve", "note": ""},
                   {"X-Reviewer": REVIEWER})
    check("通过成功并返回资料库编号", code == 200 and d.get("library_id"), f"{code} {d}")

    code, lib = call("/api/library")
    titles = [x["title"] for x in lib.get("items", [])]
    check("资料库里出现这条", "審核測試 A" in titles, str(titles[:5]))

    code, d = call(f"/api/review/uploads/{b['id']}/decide", "POST", {"action": "reject", "note": ""},
                   {"X-Reviewer": REVIEWER})
    check("退回不写理由被拒", code == 400, f"{code} {d}")

    code, d = call(f"/api/review/uploads/{b['id']}/decide", "POST",
                   {"action": "reject", "note": "重复投稿"}, {"X-Reviewer": REVIEWER})
    check("写理由后退回成功", code == 200 and d.get("ok"), f"{code} {d}")

    code, lib_pub = call("/api/library")
    item_a = next((x for x in lib_pub.get("items", []) if x["title"] == "審核測試 A"), {})
    check("勾了公开：公开接口带邮箱", item_a.get("contact") == "tester@example.com", str(item_a)[:100])

    code, lib2 = call("/api/library")
    titles2 = [x["title"] for x in lib2.get("items", [])]
    check("退回的不在资料库", "審核測試 B" not in titles2, str(titles2[:5]))

    code, lst_pending = call("/api/review/uploads", headers={"X-Reviewer": REVIEWER})
    codes_list = [x["id"] for x in lst_pending.get("items", [])]
    check("审核端仍能看到待审（链路未断）", isinstance(codes_list, list), str(codes_list[:3]))

    code, lst2 = call("/api/review/uploads", headers={"X-Reviewer": REVIEWER})
    ids2 = [x["id"] for x in lst2.get("items", [])]
    check("处理完的离开待审列表", a["id"] not in ids2 and b["id"] not in ids2, str(ids2[:5]))

    # 不公开邮箱：通过后公开接口不应返回 contact 字段
    c = upload("審核測試 C", contact_public="0")
    call(f"/api/review/uploads/{c['id']}/decide", "POST", {"action": "approve", "note": ""},
         {"X-Reviewer": REVIEWER})
    code, lib3 = call("/api/library")
    item_c = next((x for x in lib3.get("items", []) if x["title"] == "審核測試 C"), {})
    check("没勾公开：公开接口不带邮箱", bool(item_c) and "contact" not in item_c, str(item_c)[:100])
    _cleanup()

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
