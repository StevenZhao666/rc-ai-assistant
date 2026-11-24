"""条款全文检索（FTS5）测试。

    ./.venv/Scripts/python.exe tests/test_fts.py
"""
import json
import os
import sys
import time
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
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())


def main():
    t0 = time.perf_counter()
    d = get("/api/clauses?q=" + urllib.parse.quote("訪客過夜") + "&limit=3")
    dt = (time.perf_counter() - t0) * 1000
    check("接口可用", "items" in d, str(d)[:120])
    check("命中 3.2", any(x.get("anchor") == "3.2" for x in d["items"]), str(d["items"])[:120])
    check("带条款号与原文", all(x.get("anchor") and x.get("text") for x in d["items"]), "")
    check("延迟 < 200ms", dt < 200, f"{dt:.0f}ms")
    print(f"       查询耗时 {dt:.0f} ms")

    d2 = get("/api/clauses?q=" + urllib.parse.quote("寵物"))
    anchors = {x["anchor"] for x in d2["items"]}
    check("单词也能命中（宠物→17.1）", "17.1" in anchors, str(anchors))

    d3 = get("/api/clauses?q=" + urllib.parse.quote("洗衣機"))
    check("英文/长词命中（洗衣機→13.3）", any(x["anchor"] == "13.3" for x in d3["items"]), str([x["anchor"] for x in d3["items"]]))

    code = None
    try:
        get("/api/clauses?q=")
    except urllib.error.HTTPError as e:
        code = e.code
    check("空查询 400", code == 400, str(code))

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
