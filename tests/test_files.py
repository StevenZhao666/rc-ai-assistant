"""文件检索接口测试（只读，依赖已有已上架数据）。

    ./.venv/Scripts/python.exe tests/test_files.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("BASE", "http://127.0.0.1:8001").rstrip("/")
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
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main():
    code, raw = get("/api/files?limit=5")
    d = json.loads(raw)
    check("文件列表可读", code == 200 and "items" in d, str(code))
    check("有已上架文件", d.get("total", 0) > 0, str(d.get("total")))
    if not d.get("items"):
        print("没有数据，先跑一次投稿+审核")
        sys.exit(1)

    it = d["items"][0]
    fid = it["file_id"]
    check("条目带文件名与地址", bool(it.get("name")) and it.get("url", "").startswith("/files/"), str(it)[:120])

    code, raw = get("/api/files/" + str(fid))
    one = json.loads(raw)
    check("单文件可读", code == 200 and one.get("item", {}).get("file_id") == fid, str(code))

    name = it["name"].rsplit(".", 1)[0][:2]
    code, raw = get("/api/files?q=" + urllib.parse.quote(name))
    found = json.loads(raw)
    check("按文件名能搜到", found.get("total", 0) > 0, name)

    code, raw = get("/api/files?kind=work")
    w = json.loads(raw)
    check("按类型过滤有效", all(x["kind"] == "work" for x in w.get("items", [])), str(w.get("total")))

    code, body = get(it["url"])
    check("文件本身能下载", code == 200 and len(body) > 0, f"{code} {len(body)}B")

    code, raw = get("/api/files/999999")
    check("不存在的文件 404", code == 404, str(code))

    code, raw = get("/files-download/" + str(fid))
    check("下载接口可用", code == 200, str(code))

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
