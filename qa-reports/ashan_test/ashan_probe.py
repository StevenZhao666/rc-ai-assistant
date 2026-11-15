import json, urllib.request, time

QS = [
 ("退宿流程", "我大四要毕业了，退宿要走什么流程？"),
 ("退宿预约时间", "退宿前要提前几天向书院预约？"),
 ("追问-损坏", "那如果房间有损坏呢？"),
 ("损坏赔偿", "退宿时房间有损坏，比如墙上打了洞或者家具坏了，要怎么赔偿？"),
 ("追问-押金", "押金什么时候退回来？"),
 ("押金退还", "退宿的押金一般多久能退到账？会从押金里扣清洁费吗？"),
 ("追问-最晚", "最晚什么时候搬走？"),
 ("搬离截止", "毕业退宿最晚必须在几月几号之前搬离宿舍？"),
 ("续住条件", "我毕业后还想续住，续住要满足什么条件？"),
 ("追问-手续", "那要填什么表、找谁批？"),
 ("续住流程", "申请续住要交哪些材料？走哪个流程、找谁审批？"),
 ("毕业典礼住宿", "我7月才办毕业典礼，宿舍能住到典礼结束吗？暑期住宿怎么申请？"),
]

out = []
for tag, q in QS:
    payload = json.dumps({"question": q}, ensure_ascii=False).encode()
    req = urllib.request.Request("http://127.0.0.1:8001/api/ask", data=payload,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode())
    except Exception as e:
        d = {"error": str(e)}
    dt = round(time.time()-t0, 1)
    rec = {"tag": tag, "q": q, "secs": dt,
           "mode": d.get("mode"), "answer": d.get("answer"),
           "error": d.get("error"),
           "cites": [{"source": c.get("source"), "url": c.get("source_url"),
                      "score": c.get("score"), "warn": c.get("warnings"),
                      "cq": c.get("question")} for c in (d.get("citations") or [])]}
    out.append(rec)
    print(f"[{len(out)}/12] {tag} | {rec['mode']} | {dt}s")
    print("  Q:", q)
    print("  A:", (rec["answer"] or rec["error"] or "")[:400].replace("\n", " "))
    for c in rec["cites"]:
        print(f"  C: score={c['score']} src={c['source']} url={c['url']} warn={c['warn']}")
    print("-" * 70)

with open("C:/Users/风夜/Desktop/ashan_results.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("saved", len(out))
