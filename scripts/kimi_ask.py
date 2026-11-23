"""向 Kimi K3.1 提一个自定义问题（流式，边写边存）。

    python scripts/kimi_ask.py question.md
    python scripts/kimi_ask.py question.md --out data/kimi_scrape.md

输出默认 data/kimi_ask.md；中断也保留已生成部分。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = pathlib.Path.home() / "AppData/Local/hermes/config.yaml"
MODEL = "kimi-k3.1-pro"


def api_key() -> str:
    s = CFG.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"kimi:\s*\n\s*api_key:\s*(\S+)", s)
    if not m:
        raise SystemExit("config.yaml 里没找到 kimi api_key")
    return m.group(1).strip("'\"")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt_file")
    ap.add_argument("--out", default="data/kimi_ask.md")
    ap.add_argument("--max-tokens", type=int, default=8000)
    a = ap.parse_args()

    prompt = pathlib.Path(a.prompt_file).read_text(encoding="utf-8")
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 1, "max_tokens": a.max_tokens, "stream": True}).encode()
    req = urllib.request.Request("https://api.moonshot.cn/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {api_key()}"})

    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    chars = 0
    with urllib.request.urlopen(req, timeout=900) as r, out.open("w", encoding="utf-8") as f:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                d = json.loads(data)
            except Exception:
                continue
            piece = ((d.get("choices") or [{}])[0].get("delta") or {}).get("content") or ""
            if piece:
                f.write(piece)
                f.flush()
                chars += len(piece)
    print(f"{chars} 字，{time.time() - t0:.0f}s → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
