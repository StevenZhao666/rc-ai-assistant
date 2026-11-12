"""从 data/tunnel.log 里取最后一个 trycloudflare 地址，写到 data/tunnel_url.txt。"""
import pathlib
import re

root = pathlib.Path(__file__).resolve().parent.parent
log = root / "data" / "tunnel.log"
urls = re.findall(r"https://[a-z0-9-]+[.]trycloudflare[.]com",
                  log.read_text(encoding="utf-8", errors="ignore")) if log.exists() else []
if urls:
    (root / "data" / "tunnel_url.txt").write_text(urls[-1], encoding="utf-8")
    print(urls[-1])
