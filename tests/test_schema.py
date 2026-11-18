"""结构冒烟测试：在临时库里建表、插一条完整链路、验证约束。

    ./.venv/Scripts/python.exe tests/test_schema.py
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL = ROOT / "docs" / "schema-v1.sql"

PASS = FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}  {detail}")


def main() -> None:
    tmp = Path(tempfile.mkdtemp()) / "schema.db"
    conn = sqlite3.connect(tmp)
    conn.executescript(SQL.read_text(encoding="utf-8"))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')").fetchall()}
    need = {"resource", "doc", "doc_version", "clause", "qa", "qa_clause", "work",
            "work_file", "link", "link_check", "tag", "resource_tag", "review_log",
            "change_log", "client", "api_log", "glossary", "legacy_map", "v_qa"}
    check("18 张表 + 1 个视图都建了", need <= tables, str(sorted(need - tables)))

    # 公文 → 版本 → 条款
    cur = conn.execute("INSERT INTO resource (type,title,status,visibility,owner) VALUES ('doc','CKLC 住宿规章','published','public','uc99999')")
    doc_id = cur.lastrowid
    conn.execute("INSERT INTO doc (resource_id,doc_no,issuer,doc_type) VALUES (?,?,?,?)",
                 (doc_id, "CKLC/R0001/2020", "CKLC", "regulation"))
    cur = conn.execute("INSERT INTO doc_version (doc_id,version,effective_from,storage_path) VALUES (?,?,?,?)",
                       (doc_id, "AY2026-2027", "2026-08-01", "docs/2026/rules.pdf"))
    ver_id = cur.lastrowid
    cur = conn.execute("INSERT INTO clause (doc_version_id,anchor,section,variant,text) VALUES (?,?,?,?,?)",
                       (ver_id, "3.2", "3. Visitors", "zh", "訪客過夜須先獲院長許可。"))
    clause_id = cur.lastrowid

    # 条目 → 绑两条条款
    cur = conn.execute("INSERT INTO resource (type,title,status,visibility) VALUES ('qa','访客可以过夜吗','published','public')")
    qa_id = cur.lastrowid
    conn.execute("INSERT INTO qa (resource_id,question,answer,ttl_type) VALUES (?,?,?,?)",
                 (qa_id, "访客可以过夜吗", "可以，但要院长许可并付费。", "A"))
    cur = conn.execute("INSERT INTO clause (doc_version_id,anchor,section,variant,text) VALUES (?,?,?,?,?)",
                       (ver_id, "3.1", "3. Visitors", "zh", "訪客只能 9:00-22:00 逗留。"))
    clause2 = cur.lastrowid
    conn.executemany("INSERT INTO qa_clause (qa_id,clause_id,strength) VALUES (?,?,?)",
                     [(qa_id, clause_id, "direct"), (qa_id, clause2, "ref")])

    # 作品 + 附件
    cur = conn.execute("INSERT INTO resource (type,title,status,visibility,contact_public) VALUES ('work','选课助手','published','public',1)")
    work_id = cur.lastrowid
    conn.execute("INSERT INTO work (resource_id,author_id,author_name,work_type,consent,contact,contact_public) VALUES (?,?,?,?,?,?,?)",
                 (work_id, "uc12345", "小明", "tool", "yes", "uc12345@um.edu.mo", 1))
    conn.execute("INSERT INTO work_file (work_id,storage_path,mime,size_bytes) VALUES (?,?,?,?)",
                 (work_id, "works/2026/course-helper.zip", "application/zip", 204800))

    # 非官方网站 + 探活
    cur = conn.execute("INSERT INTO resource (type,title,status,visibility,source_kind) VALUES ('link','UM 选课评价站','published','public','external')")
    link_id = cur.lastrowid
    conn.execute("INSERT INTO link (resource_id,url,link_type,is_official,risk) VALUES (?,?,?,?,?)",
                 (link_id, "https://umeh.top", "student", 0, "unofficial"))
    conn.execute("INSERT INTO link_check (link_id,http_status,final_url) VALUES (?,?,?)",
                 (link_id, 200, "https://umeh.top/"))

    # 标签、客户端、术语
    conn.execute("INSERT INTO tag (name,kind) VALUES ('设施','topic')")
    conn.execute("INSERT INTO resource_tag (resource_id,tag_id) VALUES (?,1)", (link_id,))
    conn.execute("INSERT INTO client (name,kind,key_hash,scope) VALUES (?,?,?,?)",
                 ("论坛提交", "partner", "sha256:abc", "submit"))
    conn.execute("INSERT INTO glossary (term,meaning) VALUES ('HA','House Association 宿生会')")
    conn.commit()

    n = lambda sql: conn.execute(sql).fetchone()[0]
    check("公文/条目/作品/链接四类各一条",
          n("SELECT COUNT(*) FROM resource WHERE type IN ('doc','qa','work','link')") == 4)
    check("问答绑了两条条款",
          n("SELECT COUNT(*) FROM qa_clause WHERE qa_id=?", ) if False else
          conn.execute("SELECT COUNT(*) FROM qa_clause WHERE qa_id=?", (qa_id,)).fetchone()[0] == 2)
    check("作品附件只存路径不存二进制",
          n("SELECT COUNT(*) FROM work_file WHERE storage_path IS NOT NULL") == 1)
    check("非官方网站被标记 is_official=0",
          conn.execute("SELECT is_official FROM link WHERE resource_id=?", (link_id,)).fetchone()[0] == 0)
    check("兼容视图能读出问答",
          conn.execute("SELECT COUNT(*) FROM v_qa WHERE status='published'").fetchone()[0] == 1)

    # 约束：非法 type / status / scope 必须被拒
    for name, sql, args in [
        ("拒绝非法 type", "INSERT INTO resource (type,title) VALUES (?,?)", ("video", "x")),
        ("拒绝非法 status", "INSERT INTO resource (type,title,status) VALUES (?,?,?)", ("qa", "x", "live")),
        ("拒绝非法 scope", "INSERT INTO client (name,key_hash,scope) VALUES (?,?,?)", ("x", "h", "write")),
        ("拒绝非法 consent 值", "INSERT INTO work (resource_id,author_name,consent) VALUES (?,?,?)", (qa_id, "x", "maybe")),
    ]:
        try:
            conn.execute(sql, args)
            check(name, False, "居然插进去了")
        except sqlite3.IntegrityError:
            check(name, True)

    # 级联删除：删公文 → 版本 → 条款一起走
    conn.execute("DELETE FROM resource WHERE id=?", (doc_id,))
    conn.commit()
    check("删公文时版本与条款级联删除",
          n("SELECT COUNT(*) FROM doc_version") == 0 and n("SELECT COUNT(*) FROM clause") == 0)
    check("但问答本身还在（只是失去依据）",
          conn.execute("SELECT COUNT(*) FROM qa WHERE resource_id=?", (qa_id,)).fetchone()[0] == 1)

    print(f"\n{PASS} pass / {FAIL} fail / {PASS + FAIL} total")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
