"""重启 cloudflared 隧道，直到拿到一个「能真正打开」的公网地址。

为什么循环：Cloudflare 快速隧道偶尔分配到的域名只有 AAAA 记录（本地解析失败），
表现为 curl 000 / Cloudflare 530。遇到就换一个，不能把假地址给用户。

用法：.venv\Scripts\python.exe scripts\restart_tunnel.py [最多尝试次数]
"""
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOGS = ["tunnel.err", "tunnel.stdout", "tunnel.log"]
PATTERN = re.compile(r"https://[a-z0-9-]+[.]trycloudflare[.]com")


def cloudflared_pids() -> list[str]:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq cloudflared.exe"],
                         capture_output=True, text=True, errors="ignore").stdout
    return re.findall(r"cloudflared\.exe\s+(\d+)", out)


def kill_cloudflared() -> None:
    for pid in cloudflared_pids():
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
    for _ in range(20):                      # 等文件句柄释放
        if not cloudflared_pids():
            return
        time.sleep(0.5)


def mark_sizes() -> dict[str, int]:
    return {name: (DATA / name).stat().st_size if (DATA / name).exists() else 0
            for name in LOGS}


def start() -> dict[str, int]:
    marks = mark_sizes()
    out = (DATA / "tunnel.stdout").open("ab")
    err = (DATA / "tunnel.err").open("ab")
    subprocess.Popen(
        [str(ROOT / "tools" / "cloudflared.exe"), "tunnel",
         "--url", "http://127.0.0.1:8001", "--no-autoupdate",
         "--logfile", str(DATA / "tunnel.log")],
        stdout=out, stderr=err, cwd=ROOT,
        creationflags=0x08000000,
    )
    return marks


def new_text(marks: dict[str, int]) -> str:
    text = ""
    for name in LOGS:
        f = DATA / name
        if not f.exists():
            continue
        with f.open("r", encoding="utf-8", errors="ignore") as fh:
            fh.seek(marks.get(name, 0))
            text += fh.read()
    return text


def find_url(marks: dict[str, int], timeout: float = 40) -> str | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = PATTERN.findall(new_text(marks))
        if found:
            return found[-1]
        time.sleep(2)
    return None


def reachable(url: str, timeout: float = 30) -> bool:
    host = url.split("//", 1)[1].split("/", 1)[0]
    try:
        socket.getaddrinfo(host, 443, socket.AF_INET)     # 必须有 IPv4
    except socket.gaierror:
        return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url + "/health", headers={"User-Agent": "rc-check"})
            with urllib.request.urlopen(req, timeout=8) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def main() -> int:
    tries = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    for i in range(1, tries + 1):
        kill_cloudflared()
        marks = start()
        url = find_url(marks)
        if not url:
            print(f"[{i}] 没拿到地址，重试")
            continue
        if reachable(url):
            (DATA / "tunnel_url.txt").write_text(url, encoding="utf-8")
            print(f"[{i}] 可用：{url}")
            return 0
        print(f"[{i}] {url} 打不开（可能只有 IPv6），换一个")
    print("多次尝试都失败：检查网络，或重新下载 tools/cloudflared.exe")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
