import json, urllib.request, time
QS = [
 ("押金是否存在", "书院住宿要交押金吗？押金是多少钱？"),
 ("赔偿金额表", "宿舍损坏赔偿的具体金额表在哪里可以查到？"),
 ("退宿交回物品", "退宿时要交回哪些东西？房卡丢了怎么办？"),
 ("住宿费退还", "提前退宿的话住宿费会退吗？按什么标准退？"),
]
for tag, q in QS:
    payload = json.dumps({"question": q}, ensure_ascii=False).encode()
    req = urllib.request.Request("http://127.0.0.1:8001/api/ask", data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode())
    except Exception as e:
        d = {"error": str(e)}
    print("==", tag, "|", d.get("mode"), "|", q)
    print("A:", (d.get("answer") or d.get("error"))[:500].replace("\n", " "))
    for c in (d.get("citations") or []):
        print("   C:", c.get("score"), c.get("source"), c.get("source_url"), c.get("warnings"))
    print()
