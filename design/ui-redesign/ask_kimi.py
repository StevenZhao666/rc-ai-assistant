# -*- coding: utf-8 -*-
"""Ask Kimi K3.1 for a second opinion on one file of brief text.

usage: python ask_kimi.py <prompt.md> [out.md]
"""
import json, pathlib, re, sys, time, urllib.request

CFG = pathlib.Path.home() / "AppData/Local/hermes/config.yaml"
MODEL = "kimi-k3.1-pro"


def api_key() -> str:
    s = CFG.read_text(encoding="utf-8", errors="ignore")
    return re.search(r"kimi:\s*\n\s*api_key:\s*(\S+)", s).group(1).strip("'\"")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: ask_kimi.py <prompt.md> [out.md]")
        return 2
    prompt = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
    out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "kimi_ui.md")

    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1,
        "max_tokens": 32000,
        "stream": True,
    }).encode()
    req = urllib.request.Request(
        "https://api.moonshot.cn/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key()}"})

    t0 = time.time()
    chunks = []
    out.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=600) as r, out.open("w", encoding="utf-8") as f:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                j = json.loads(data)
            except Exception:
                continue
            delta = (j.get("choices") or [{}])[0].get("delta") or {}
            piece = delta.get("content")
            if piece:
                chunks.append(piece)
                f.write(piece)
                f.flush()
    print("wrote %s (%d chars, %.0fs)" % (out, sum(len(c) for c in chunks), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
