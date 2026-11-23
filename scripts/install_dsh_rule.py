"""把「书院问题先跑 ask.bat」这条规则写进 dsh 的配置。

    python scripts/install_dsh_rule.py           # 安装 / 覆盖
    python scripts/install_dsh_rule.py --remove  # 移除
    python scripts/install_dsh_rule.py --show    # 看看现在写了什么

改的是 %USERPROFILE%\\.dsh-rust\\settings.toml 的 custom_instructions 字段，
改之前在同目录留一份 .bak-shuyuan。dsh 的下一个会话生效（已开的会话要重开）。
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

RULE = (
    "问及澳门大学张昆仑书院（CKLC）的任何事情时，第一步必须先运行 shell 命令 "
    'D:/Projects/rc-ai-assistant/ask.bat "<用户原问题>" ，然后把它的输出原样转述给用户，'
    "保留「依据 N · 条目」那几行；禁止自己查数据库、grep 文件或凭记忆回答；"
    "如果脚本报连不上，提示用户运行 D:/Projects/rc-ai-assistant/scripts/start_all.bat。"
)


def settings_path() -> Path:
    home = os.environ.get("DSH_HOME") or str(Path.home() / ".dsh-rust")
    return Path(home) / "settings.toml"


def toml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def read_value(text: str) -> str:
    m = re.search('^custom_instructions\\s*=\\s*"([^\\n]*)"\\s*$', text, re.M)
    return m.group(1) if m else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--rule", default=RULE, help="自定义规则文本")
    a = ap.parse_args()

    p = settings_path()
    if not p.exists():
        print(f"没找到 dsh 配置：{p}\n先装 dsh（https://www.deepseek.com/en/harness/），再回来跑这个脚本。")
        return 1

    text = p.read_text(encoding="utf-8")
    if a.show:
        print(read_value(text) or "(空)")
        return 0

    backup = p.with_name(f"settings.toml.bak-shuyuan-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(p, backup)

    new_val = "" if a.remove else toml_escape(a.rule)
    line = f'custom_instructions = "{new_val}"'
    if re.search(r"^custom_instructions\s*=.*$", text, re.M):
        text = re.sub(r"^custom_instructions\s*=.*$", line, text, count=1, flags=re.M)
    else:
        text = text.rstrip("\n") + "\n" + line + "\n"
    p.write_text(text, encoding="utf-8")

    print(("已移除" if a.remove else "已写入") + f"：{p}")
    print(f"备份：{backup.name}")
    print("dsh 新开会话生效。验证：dsh exec \"洗衣房在哪一層？\" 应输出「依据 1 · 条目 …」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
