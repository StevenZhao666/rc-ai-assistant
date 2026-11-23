"""把本机资料库的示例数据同步到服务器（只搬 library_item / upload_file 和对应文件）。

    python scripts/sync_demo_data.py --dry-run
    python scripts/sync_demo_data.py

不动服务器上的 kb_item / chunk（问答与条款是服务器自己的）。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "kb.sqlite3"
FILES = ROOT / "data" / "files"
HOST = os.environ.get("DEPLOY_HOST", "159.75.225.125")
USER = os.environ.get("DEPLOY_USER", "root")
REMOTE = os.environ.get("DEPLOY_PATH", "/opt/rc-ai")
KEY = Path(os.environ.get("DEPLOY_KEY", Path.home() / ".ssh" / "rc_ai_deploy"))
TABLES = ("upload_file", "library_item")


def dump_sql() -> tuple[str, list[str]]:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    out = ["BEGIN;"]
    paths: list[str] = []
    for t in TABLES:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
        for row in con.execute(f"SELECT * FROM {t}"):
            vals = []
            for c in cols:
                v = row[c]
                if v is None:
                    vals.append("NULL")
                elif isinstance(v, (int, float)):
                    vals.append(str(v))
                else:
                    vals.append("'" + str(v).replace("'", "''") + "'")
            out.append(f"INSERT OR REPLACE INTO {t} ({','.join(cols)}) VALUES ({','.join(vals)});")
            if t == "upload_file" and row["path"]:
                paths.append(str(row["path"]))
    out.append("COMMIT;")
    return "\n".join(out), paths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    sql, paths = dump_sql()
    rel = [p.replace("\\", "/").split("files/", 1)[-1] for p in paths]
    print(f"要同步：{len(paths)} 个文件，两条表")
    for r in rel:
        print("  -", r)

    if a.dry_run:
        print("SQL 行数：", sql.count("\n"))
        return 0

    tmp = Path(tempfile.gettempdir())
    (tmp / "_sync.sql").write_text(sql, encoding="utf-8")
    tar_path = tmp / "_sync_files.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        for r in rel:
            f = FILES / r
            if f.exists():
                tf.add(f, arcname=r)

    def scp(local: Path, remote: str) -> None:
        r = subprocess.run(["scp", "-i", str(KEY), "-o", "StrictHostKeyChecking=no",
                            str(local), f"{USER}@{HOST}:{remote}"], capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print("scp 失败：", r.stderr[-400:])
            sys.exit(1)

    scp(tmp / "_sync.sql", f"{REMOTE}/_sync.sql")
    if rel:
        scp(tar_path, f"{REMOTE}/_sync_files.tar.gz")

    cmd = (f"cd {REMOTE} && mkdir -p data/files && "
           + ("tar xzf _sync_files.tar.gz -C data/files/ && rm -f _sync_files.tar.gz; " if rel else "")
           + ".venv/bin/python -c \"import sqlite3;c=sqlite3.connect('data/kb.sqlite3');"
             "c.executescript(open('_sync.sql').read());c.commit();"
             "print('library_item', c.execute('select count(*) from library_item').fetchone()[0],"
             "'upload_file', c.execute('select count(*) from upload_file').fetchone()[0])\"; rm -f _sync.sql")
    r = subprocess.run(["ssh", "-i", str(KEY), "-o", "StrictHostKeyChecking=no", f"{USER}@{HOST}", cmd],
                       capture_output=True, text=True, timeout=300)
    print(r.stdout.strip() or r.stderr[-400:])
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
