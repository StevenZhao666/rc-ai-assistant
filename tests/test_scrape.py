"""反扒测试：公开接口限速 + 页面不被索引。

    ./.venv/Scripts/python.exe tests/test_scrape.py

注意：会把本机该 IP 的配额打满一分钟，跑完等一分钟再点网页。
"""
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("BASE", "http://127.0.0.1:8001").rstrip("/")
LIMIT = int(os.environ.get("SCRAPE_LIMIT_PER_MIN", "60"))
BURST = int(os.environ.get("SCRAPE_BURST", "20"))
PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}  {detail}")


def low(h: dict) -> dict:
    return {str(k).lower(): v for k, v in h.items()}


def get(path, headers=None):
    req = urllib.request.Request(BASE + path, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, low(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, low(e.headers), e.read()


def main():
    code, hdr, _ = get("/api/library?limit=1")
    check("正常请求 200", code == 200, str(code))
    check("带 X-Robots-Tag", "noindex" in (hdr.get("x-robots-tag") or ""), str(hdr.get("x-robots-tag")))

    check("带 nosniff", "nosniff" in (hdr.get("x-content-type-options") or ""), str(hdr.get("x-content-type-options")))
    check("公开接口可缓存 60s", "max-age=60" in (hdr.get("cache-control") or ""), str(hdr.get("cache-control")))

    code, hdr, _ = get("/library")
    body = (get("/library")[2] or b"").decode("utf-8", "ignore")
    check("资料库页 noindex", 'name="robots"' in body and "noindex" in body, "")
    check("页面也带 X-Robots-Tag", "noindex" in (hdr.get("x-robots-tag") or ""), str(hdr.get("x-robots-tag")))

    # 用独立 X-Forwarded-For 避开真实 IP 的计数
    fake_ip = "10.99.99.99"
    hit429 = None
    for i in range(BURST + LIMIT + 5):
        code, hdr, body = get("/api/library?limit=1", {"X-Forwarded-For": fake_ip})
        if code == 429:
            hit429 = (i + 1, hdr, body)
            break
    check("超过限额返回 429", hit429 is not None, f"打了 {BURST + LIMIT + 5} 次没触发")
    if hit429:
        n, hdr, body = hit429
        check("429 带 Retry-After", "retry-after" in hdr, str(hdr))
        print(f"       第 {n} 次被拦")

    # 别的 IP 不受影响
    code, _, _ = get("/api/library?limit=1", {"X-Forwarded-For": "10.99.99.100"})
    check("换 IP 仍可用", code == 200, str(code))

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
