"""用密码登一次，装公钥 + 摸清服务器底细。密码只从环境变量读，不落盘。

用法：
    SSH_PASS=****** .venv\\Scripts\\python.exe scripts/ssh_probe.py
"""
import os
import sys
from pathlib import Path

import paramiko

HOST = os.environ.get("PROBE_HOST", "127.0.0.1")
USER = "root"
PUB = (Path.home() / ".ssh" / "rc_ai_deploy.pub").read_text(encoding="utf-8").strip()

CMDS = [
    ("系统", "cat /etc/os-release | head -2"),
    ("内核", "uname -r"),
    ("Python", "python3 -V 2>&1; python3.11 -V 2>&1"),
    ("磁盘", "df -h / | tail -1"),
    ("内存", "free -m | head -2"),
    ("已占端口", "ss -lntp | grep -E ':(80|443|8090|8091)\\b' || echo none"),
    ("防火墙端口", "firewall-cmd --list-ports 2>/dev/null || echo 'firewalld 未运行'"),
    ("网站目录", "ls -d /www/wwwroot/* 2>/dev/null || echo none"),
]


def main() -> int:
    pwd = os.environ.get("SSH_PASS", "")
    if not pwd:
        print("缺少 SSH_PASS")
        return 2
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(HOST, username=USER, password=pwd, timeout=20, allow_agent=False, look_for_keys=False)
    except paramiko.AuthenticationException:
        print("认证失败：密码不对")
        return 1

    for label, cmd in CMDS:
        _, out, err = c.exec_command(cmd, timeout=20)
        text = (out.read().decode("utf-8", "ignore") + err.read().decode("utf-8", "ignore")).strip()
        print(f"[{label}]\n{text}\n")

    # 装公钥（幂等）
    _, out, _ = c.exec_command("mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys", timeout=15)
    out.read()
    _, out, _ = c.exec_command(f"grep -qF '{PUB}' ~/.ssh/authorized_keys && echo EXISTS || "
                               f"(echo '{PUB}' >> ~/.ssh/authorized_keys && echo ADDED)", timeout=15)
    print("[公钥]", out.read().decode().strip())
    c.exec_command("chmod 600 ~/.ssh/authorized_keys")[1].read()
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
