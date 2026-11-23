"""把本机代码同步到服务器并重启。

    python scripts/deploy.py --dry-run     # 只列要传什么、要跑什么
    python scripts/deploy.py               # 真部署

只传代码，不碰服务器上的 data/ 和 .env：
    app/ scripts/ tests/ docs/ mcp_server.py ask.py requirements.txt

部署后自动验证：/health、/api/library、/library 页。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = os.environ.get("DEPLOY_HOST", "159.75.225.125")
USER = os.environ.get("DEPLOY_USER", "root")
REMOTE = os.environ.get("DEPLOY_PATH", "/opt/rc-ai")
KEY = Path(os.environ.get("DEPLOY_KEY", Path.home() / ".ssh" / "rc_ai_deploy"))
INCLUDE = ["app", "scripts", "tests", "docs", "mcp_server.py", "mcp_files_server.py", "ask.py", "requirements.txt"]


def ssh(cmd: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ssh", "-i", str(KEY), "-o", "StrictHostKeyChecking=no", f"{USER}@{HOST}", cmd],
        capture_output=True, text=True, timeout=timeout)


def build_tarball() -> Path:
    tmp = Path(tempfile.gettempdir()) / "rc-ai-deploy.tar.gz"
    with tarfile.open(tmp, "w:gz") as tf:
        for item in INCLUDE:
            p = ROOT / item
            if not p.exists():
                print(f"  跳过（不存在）：{item}")
                continue
            tf.add(p, arcname=item,
                   filter=lambda ti: None if "__pycache__" in ti.name or ti.name.endswith(".pyc") else ti)
    return tmp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not KEY.exists():
        print(f"找不到密钥：{KEY}")
        return 1

    print(f"目标：{USER}@{HOST}:{REMOTE}")
    print("打包：", ", ".join(INCLUDE))
    steps = [
        "服务器上先备份现有 app/ 与 mcp_server.py 到 backups/",
        f"scp 包到 {REMOTE}/_deploy.tar.gz",
        f"解包到 {REMOTE}（覆盖同名代码，data/ 与 .env 不动）",
        f"{REMOTE}/.venv/bin/pip install -r requirements.txt",
        "systemctl restart rc-ai",
        "curl /health、/api/library、/library",
    ]
    if a.dry_run:
        for s in steps:
            print("  -", s)
        tar = build_tarball()
        print(f"本机试打包成功：{tar}（{tar.stat().st_size // 1024} KB）")
        return 0

    tar = build_tarball()
    print(f"包：{tar}（{tar.stat().st_size // 1024} KB）")

    def run(cmd: str, label: str, timeout: int = 300) -> bool:
        r = ssh(cmd, timeout=timeout)
        ok = r.returncode == 0
        print(f"[{'OK' if ok else 'FAIL'}] {label}")
        if not ok:
            print((r.stdout or "")[-800:])
            print((r.stderr or "")[-800:])
        return ok

    cp = subprocess.run(
        ["scp", "-i", str(KEY), "-o", "StrictHostKeyChecking=no", str(tar), f"{USER}@{HOST}:{REMOTE}/_deploy.tar.gz"],
        capture_output=True, text=True, timeout=600)
    print(f"[{'OK' if cp.returncode == 0 else 'FAIL'}] 上传")
    if cp.returncode != 0:
        print(cp.stderr[-800:])
        return 1

    if not run(f"cd {REMOTE} && mkdir -p backups && tar czf backups/code-$(date +%Y%m%d-%H%M%S).tar.gz"
               f" app mcp_server.py 2>/dev/null; ls -t backups/code-*.tar.gz | head -1", "服务器备份"):
        print("  备份失败，先不覆盖")
        return 1
    if not run(f"cd {REMOTE} && tar xzf _deploy.tar.gz && rm -f _deploy.tar.gz", "解包"):
        return 1
    if not run(f"cd {REMOTE} && .venv/bin/pip install -q -r requirements.txt", "装依赖", timeout=600):
        return 1
    restart = ("systemctl restart rc-ai; "
               "for i in $(seq 1 20); do s=$(systemctl is-active rc-ai); "
               "if [ \"$s\" = active ]; then echo active; exit 0; fi; sleep 1; done; "
               "echo \"not active: $(systemctl is-active rc-ai)\"; journalctl -u rc-ai -n 15 --no-pager; exit 1")
    if not run(restart, "重启服务", timeout=120):
        return 1

    checks = {
        "健康检查": "curl -s -m 8 http://127.0.0.1:8091/health",
        "资料库接口": "curl -s -m 8 'http://127.0.0.1:8091/api/library?kind=work' | head -c 120",
        "资料库页面": "curl -s -m 8 -o /dev/null -w '%{http_code}' http://127.0.0.1:8091/library",
    }
    all_ok = True
    for name, cmd in checks.items():
        r = ssh(cmd)
        body = (r.stdout or "").strip().replace("\n", " ")[:160]
        ok = r.returncode == 0 and ("ok" in body.lower() or body.isdigit() and body.startswith("200")
                                    or "items" in body)
        print(f"[{'OK' if ok else 'FAIL'}] {name}：{body[:140]}")
        all_ok &= bool(ok)

    print("\n部署完成。" if all_ok else "\n有检查没过，看上面的输出。")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
