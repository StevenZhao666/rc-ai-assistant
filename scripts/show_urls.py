"""打印当前可用的访问地址（公网 + 本机）。给 start_all.bat 调用。"""
import pathlib
import re
import time

root = pathlib.Path(__file__).resolve().parent.parent


def scan() -> list[str]:
    text = ""
    for name in ("tunnel.err", "tunnel.stdout", "tunnel.out", "tunnel.log"):
        f = root / "data" / name
        if f.exists():
            text += f.read_text(encoding="utf-8", errors="ignore")
    return re.findall(r"https://[a-z0-9-]+[.]trycloudflare[.]com", text)


saved = root / "data" / "tunnel_url.txt"
urls: list[str] = [saved.read_text(encoding="utf-8").strip()] if saved.exists() else []
for _ in range(0 if urls else 15):          # 最多等 ~30 秒
    urls = scan()
    if urls:
        break
    time.sleep(2)

print("=" * 48)
if urls:
    u = urls[-1]
    (root / "data" / "tunnel_url.txt").write_text(u, encoding="utf-8")
    print("  公网地址（手机用这两个，直接复制）")
    print("=" * 48)
    print(f"  学生问答： {u}/")
    print(f"  审批后台： {u}/review")
else:
    print("  [未取到公网地址] 隧道可能还没连上")
    print("  等 10 秒后再跑一次 scripts/start_all.bat")
print("=" * 48)
print("  本机（只在这台电脑上）")
print("=" * 48)
print("  学生问答： http://127.0.0.1:8001/")
print("  审批后台： http://127.0.0.1:8001/review")
