# -*- coding: utf-8 -*-
"""生成今日汇报 PPT：CKLC 资料库进展。"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "deliverables", "汇报")
os.makedirs(OUT, exist_ok=True)

RED = RGBColor(0x8A, 0x14, 0x20)
RED2 = RGBColor(0xB3, 0x26, 0x33)
INK = RGBColor(0x22, 0x1C, 0x1A)
DIM = RGBColor(0x6D, 0x62, 0x5D)
LINE = RGBColor(0xE2, 0xD8, 0xD2)
BG = RGBColor(0xFB, 0xF8, 0xF6)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
OK = RGBColor(0x2F, 0x6B, 0x4F)
WARN = RGBColor(0x8A, 0x61, 0x00)

FONT = "Microsoft YaHei"
MONO = "Consolas"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def slide(bg=BG):
    s = prs.slides.add_slide(BLANK)
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    r.fill.solid(); r.fill.fore_color.rgb = bg; r.line.fill.background()
    r.shadow.inherit = False
    return s


def txt(s, x, y, w, h, text, size=18, color=INK, bold=False, mono=False,
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.0):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = 0; tf.margin_top = tf.margin_bottom = 0
    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.line_spacing = spacing
        r = p.add_run(); r.text = line
        r.font.size = Pt(size); r.font.bold = bold
        r.font.color.rgb = color
        r.font.name = MONO if mono else FONT
    return tb


def box(s, x, y, w, h, fill=WHITE, line=LINE, radius=0.04):
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    b.adjustments[0] = radius
    b.fill.solid(); b.fill.fore_color.rgb = fill
    b.line.color.rgb = line; b.line.width = Pt(0.75)
    b.shadow.inherit = False
    return b


def head(s, kicker, title, sub=""):
    txt(s, 0.75, 0.5, 8, 0.3, kicker.upper(), 11, RED, True)
    txt(s, 0.75, 0.82, 11.8, 0.62, title, 28, INK, True)
    if sub:
        txt(s, 0.75, 1.52, 11.8, 0.4, sub, 13, DIM)


def foot(s, n):
    txt(s, 0.75, 7.02, 8, 0.25, "CKLC 资料库 · 2026-11-24", 9, DIM)
    txt(s, 12.1, 7.02, 0.5, 0.25, f"{n:02d}", 9, DIM, align=PP_ALIGN.RIGHT)


# 01 封面
s = slide(RED)
txt(s, 0.9, 1.15, 3.2, 0.3, "CKLC · 资料库与问答助手", 12, RGBColor(0xFF, 0xD9, 0xDD), True)
txt(s, 0.9, 1.55, 9.5, 1.6, "从「能答」到「有库」", 44, WHITE, True)
txt(s, 0.9, 2.55, 9.5, 1.6, "资料库主体、版本契约、全文检索与对外接口", 22, RGBColor(0xFF, 0xE6, 0xE8))
txt(s, 0.9, 5.55, 6, 0.3, "2026-11-24 · 汇报版 · 简体", 12, RGBColor(0xFF, 0xD9, 0xDD))
txt(s, 0.9, 5.95, 6, 0.3, "澳门大学 张昆仑书院（CKLC）", 12, RGBColor(0xFF, 0xD9, 0xDD))

# 02 今天做完的六件事
s = slide(); head(s, "TODAY", "今天做完的六件事", "每一项都有可执行的验证，不是“应该能用”")
items = [
    ("资料库主体", "投稿 → 审核 → 上架 → 浏览 → 下载，公网可用"),
    ("文件检索 + MCP", "cklc-files 三个工具，公网 /ai/mcp-files"),
    ("版本契约", "uid / revision / content_hash / 生效期，引用可追溯"),
    ("条款全文检索", "FTS5 中文二元组分词，3–5 ms 命中条款"),
    ("反扒与预算", "令牌桶限速、禁索引、模型日预算熔断"),
    ("公网 MCP", "/ai/mcp 五工具，外部客户端实测通过"),
]
for i, (t, d) in enumerate(items):
    x = 0.75 + (i % 3) * 4.05
    y = 2.05 + (i // 3) * 2.15
    box(s, x, y, 3.8, 1.85)
    txt(s, x + 0.25, y + 0.22, 3.3, 0.3, f"0{i+1}", 10, RED, True, mono=True)
    txt(s, x + 0.25, y + 0.55, 3.3, 0.35, t, 16, INK, True)
    txt(s, x + 0.25, y + 0.98, 3.3, 0.7, d, 11, DIM)
foot(s, 2)

# 03 资料库主体
s = slide(); head(s, "PRODUCT", "资料库主体：一条内容怎么走进去", "每一环都能在公网复现")
steps = [("投稿", "/upload\n邀请码 · 邮箱必填"), ("候选池", "candidate\npending"),
         ("审核", "/review?tab=uploads\n通过 / 退回"), ("上架", "library_item\npublished"),
         ("对外", "/library · /api/search\n· /files 下载")]
for i, (t, d) in enumerate(steps):
    x = 0.75 + i * 2.45
    box(s, x, 2.15, 2.05, 1.75)
    txt(s, x + 0.18, 2.32, 1.7, 0.3, f"0{i+1}", 10, RED, True, mono=True)
    txt(s, x + 0.18, 2.62, 1.7, 0.3, t, 15, INK, True)
    txt(s, x + 0.18, 3.0, 1.75, 0.8, d, 9.5, DIM)
    if i < 4:
        txt(s, x + 2.05, 2.85, 0.4, 0.4, "→", 16, RED)
txt(s, 0.75, 4.35, 11.8, 0.35, "线上状态", 12, DIM, True)
box(s, 0.75, 4.72, 11.8, 1.35, WHITE, LINE)
rows = [("资料库", "23 条测试数据已全部下架（archived），等真投稿", WARN),
        ("后端", "3 个 systemd 单元：rc-ai(8091) / rc-ai-mcp(8092) / rc-ai-mcp-files(8093)", OK),
        ("验证", "test_upload 14 / test_library 13 / test_public 11 / test_files 9", OK)]
for i, (k, v, c) in enumerate(rows):
    txt(s, 1.0, 4.9 + i * 0.36, 1.2, 0.3, k, 11, c, True)
    txt(s, 2.2, 4.9 + i * 0.36, 10.1, 0.3, v, 11, INK)
foot(s, 3)

# 04 版本契约
s = slide(); head(s, "TRACEABILITY", "版本契约：每个答案都能追到「哪一版」", "不是加个字段，是把“可复现”变成硬约束")
box(s, 0.75, 2.05, 5.6, 3.5)
txt(s, 1.0, 2.25, 5.1, 0.3, "每条内容的身份", 14, INK, True)
lines = [
    ("uid", "kb-0009 / chunk-0261，永不变"),
    ("revision", "内容真变才 +1，改备注不算"),
    ("content_hash", "sha1 前 12 位，判断是否真的变了"),
    ("effective_from / to", "生效区间，过期自动退出检索"),
    ("历史", "kb_revision / chunk_revision 留旧版"),
]
for i, (k, v) in enumerate(lines):
    txt(s, 1.0, 2.7 + i * 0.55, 1.9, 0.3, k, 11, RED, True, mono=True)
    txt(s, 2.95, 2.7 + i * 0.55, 3.2, 0.4, v, 10.5, DIM)
box(s, 6.7, 2.05, 5.85, 3.5)
txt(s, 6.95, 2.25, 5.3, 0.3, "线上实际返回", 14, INK, True)
txt(s, 6.95, 2.7, 5.3, 2.2,
    'GET /ai/api/qa/9\n{\n  "uid": "kb-0009",\n  "revision": 1,\n  "content_hash": "2d0a57dbc4a4",\n  "effective_from": null,\n  ...\n}', 10.5, INK, mono=True, spacing=1.15)
txt(s, 0.75, 5.85, 11.8, 0.9, "引用卡片会显示「kb-0009 v1」；学生申诉时能对上号，换模型/换检索也不用重洗历史。", 12, DIM)
foot(s, 4)

# 05 FTS5
s = slide(); head(s, "SEARCH", "条款全文检索：为什么是 FTS5，不是向量库", "先算清楚规模和成本，再决定用什么")
box(s, 0.75, 2.0, 5.7, 3.7)
txt(s, 1.0, 2.18, 5.2, 0.3, "试过但不行的两种分词", 13, INK, True)
txt(s, 1.0, 2.6, 5.2, 2.8,
    "unicode61：连续汉字当一个词，\n“訪客過夜”什么都搜不到\n\n"
    "trigram：只能搜 3 字以上，\n“寵物”“洗衣”这类 2 字词直接漏\n\n"
    "→ 自建二元组分词：\n未經書院院長 → 未經 經書 書院 院院 院長", 11, DIM, spacing=1.25)
box(s, 6.75, 2.0, 5.8, 3.7)
txt(s, 7.0, 2.18, 5.3, 0.3, "实测", 13, INK, True)
data = [("訪客 過夜", "3.2（只此一条）"), ("寵物", "17.1 中英两条"), ("洗衣機", "13.3"), ("换房", "5.1")]
for i, (q, r) in enumerate(data):
    txt(s, 7.0, 2.65 + i * 0.48, 2.2, 0.3, q, 11, RED, mono=True)
    txt(s, 9.2, 2.65 + i * 0.48, 3.1, 0.3, r, 11, INK)
txt(s, 7.0, 4.75, 5.2, 0.7, "单次 3–5 ms；查询先 AND 后 OR，兼顾准与全。", 11, DIM)
txt(s, 0.75, 5.95, 11.8, 0.9, "向量库解决的是“换说法”，解决不了“没内容”，也解决不了打分噪声；当前 368 条条款 + 119 条问答，词面检索够用。", 12, DIM)
foot(s, 5)

# 06 反扒 + 预算
s = slide(); head(s, "SAFETY", "两个闸门：别被刷爆，也别被扒光", "公开库挡不住复制，能保的是可用性、带宽与隐私")
box(s, 0.75, 2.05, 5.75, 3.35)
txt(s, 1.0, 2.25, 5.2, 0.3, "反扒", 14, INK, True)
for i, line in enumerate(["令牌桶：攒 20 个、每分钟补 60", "/api/search 一次计 3 个令牌",
                          "/files 下载也纳入限速", "X-Robots-Tag: noindex", "上传的 svg/html 强制下载"]):
    txt(s, 1.0, 2.7 + i * 0.5, 5.2, 0.3, "· " + line, 11, DIM)
box(s, 6.85, 2.05, 5.7, 3.35)
txt(s, 7.1, 2.25, 5.2, 0.3, "预算熔断", 14, INK, True)
txt(s, 7.1, 2.7, 5.2, 2.4,
    "LLM_DAILY_TOKENS 默认 300 万\n当天用量从 llm_usage.jsonl 汇总\n超了不再调模型，自动降级为原文摘录\n\n以前只有每人每小时 10 次，没有全局上限", 11, DIM, spacing=1.3)
txt(s, 0.75, 5.7, 11.8, 1.0, "验证：test_scrape 9/9（真打满触发 429、换 IP 不受影响）；预算熔断不影响正常回答，只停新增模型调用。", 12, DIM)
foot(s, 6)

# 07 两个项目
s = slide(); head(s, "ARCHITECTURE", "两个项目：代码分开，数据连着", "同一个进程、同一份 SQLite，但不互相 import")
box(s, 0.75, 1.95, 5.6, 1.55, WHITE, RED)
txt(s, 1.0, 2.12, 5.1, 0.3, "A · 崑崑问答", 15, INK, True)
txt(s, 1.0, 2.5, 5.1, 0.85, "页面 /\n读 kb_item + chunk\n/api/ask · /api/search", 10.5, DIM)
box(s, 6.95, 1.95, 5.6, 1.55, WHITE, OK)
txt(s, 7.2, 2.12, 5.1, 0.3, "B · CKLCdb 资料库", 15, INK, True)
txt(s, 7.2, 2.5, 5.1, 0.85, "页面 /library /upload /review\n读写 library_item + upload_file\n/api/library · /api/files · /api/upload", 10.5, DIM)
box(s, 0.75, 3.75, 11.8, 1.05, RGBColor(0xF1, 0xEB, 0xE7), LINE)
txt(s, 1.0, 3.92, 11.3, 0.7, "共用底座：db.py · auth.py · i18n.py · config.py　＋　同一个 data/kb.sqlite3\n主数据表分开；流程表共用（candidate、review_log）", 11, INK)
txt(s, 0.75, 5.0, 11.8, 0.85, "不 import 对方的路由模块：避免循环依赖、把上传/审核的依赖拖进问答链路、以及“问答代码顺手能写库”的越权风险。", 12, DIM)
foot(s, 7)

# 08 接口
s = slide(); head(s, "INTERFACES", "对外接口：读的齐了，写的还只有人能走", "MCP 只读，已上线；写接口缺身份")
table_rows = [
    ("读", "GET /api/search · /api/library · /api/files", "线上"),
    ("读", "GET /api/qa/{id} · /api/clauses · /api/clause · /api/updates", "线上"),
    ("写", "POST /api/upload（邀请码）", "线上"),
    ("写", "POST /api/review/uploads/{id}/decide（X-Reviewer）", "可伪造"),
    ("写", "API Key / 配额 / 写 MCP", "未做"),
]
for i, (k, v, st) in enumerate(table_rows):
    y = 1.95 + i * 0.62
    box(s, 0.75, y, 8.2, 0.52, WHITE, LINE)
    txt(s, 0.95, y + 0.12, 0.6, 0.3, k, 10, RED if k == "写" else OK, True)
    txt(s, 1.6, y + 0.12, 5.6, 0.3, v, 10, INK, mono=True)
    c = OK if st == "线上" else (WARN if st == "可伪造" else RED2)
    txt(s, 7.45, y + 0.12, 1.3, 0.3, st, 10, c, True)
box(s, 9.2, 1.95, 3.35, 1.95, RGBColor(0xF7, 0xFD, 0xF9), RGBColor(0xC9, 0xE2, 0xD3))
txt(s, 9.4, 2.1, 3.0, 0.3, "MCP（只读）", 12, OK, True)
txt(s, 9.4, 2.45, 3.0, 1.3, "/ai/mcp\n5 个工具\n\n/ai/mcp-files\n3 个工具", 10, INK)
txt(s, 0.75, 5.25, 11.8, 0.9, "缺口按风险：① X-Reviewer 可伪造　② 全站 HTTP　③ 无按项目配额", 13, RED2, True)
foot(s, 8)

# 09 线上状态
s = slide(); head(s, "STATUS", "线上现在是什么样", "地址：http://159.75.225.125/ai/")
stats = [("问答条目", "119", "已发布"), ("规章条款", "368", "FTS5 已建索引"),
         ("资料库", "0", "测试数据已下架"), ("MCP 工具", "8", "5 + 3，全部只读")]
for i, (k, v, d) in enumerate(stats):
    x = 0.75 + i * 3.02
    box(s, x, 1.95, 2.8, 1.75)
    txt(s, x + 0.22, 2.12, 2.4, 0.3, k, 11, DIM)
    txt(s, x + 0.22, 2.45, 2.4, 0.6, v, 30, RED, True)
    txt(s, x + 0.22, 3.18, 2.4, 0.3, d, 10, DIM)
txt(s, 0.75, 4.1, 11.8, 0.3, "测试基线（每次改动后跑）", 12, DIM, True)
tests = [("smoke", "25/25"), ("public", "11/11"), ("mcp", "9/9"), ("fts", "7/7"),
         ("scrape", "9/9"), ("files", "9/9"), ("versions", "12/12"), ("eval", "27/30")]
for i, (k, v) in enumerate(tests):
    x = 0.75 + (i % 4) * 3.02
    y = 4.5 + (i // 4) * 0.72
    txt(s, x, y, 1.4, 0.3, k, 11, INK, mono=True)
    txt(s, x + 1.4, y, 1.2, 0.3, v, 11, OK if "27" not in v else WARN, True, mono=True)
foot(s, 9)

# 10 下一步
s = slide(); head(s, "NEXT", "接下来：先补内容，再补身份", "把“能演示”变成“能交给书院”")
todo = [("1", "补内容", "饭堂、快递、门禁、收费/押金；有文件就入库，没有就照官网写"),
        ("2", "写接口鉴权", "X-Reviewer 换成反代 Basic Auth 或签名令牌，配审计"),
        ("3", "域名 + HTTPS", "现在裸 IP + HTTP；投稿邮箱与提问内容明文"),
        ("4", "按项目配额", "外部调用要能分账，而不是共用一个 IP 限速"),
        ("5", "数据迁移/视图", "两库合并或统一只读视图，字段契约固化")]
for i, (n, t, d) in enumerate(todo):
    y = 1.95 + i * 0.92
    txt(s, 0.85, y + 0.12, 0.5, 0.35, n, 14, RED, True, mono=True)
    txt(s, 1.45, y + 0.08, 2.2, 0.35, t, 14, INK, True)
    txt(s, 3.7, y + 0.12, 8.7, 0.5, d, 11, DIM)
foot(s, 10)

# 11 结尾
s = slide(RED)
txt(s, 0.9, 2.2, 10, 1.2, "一句话总结", 16, RGBColor(0xFF, 0xD9, 0xDD), True)
txt(s, 0.9, 2.8, 11.5, 1.8, "问答已经能答，资料库已经有了骨架；\n现在缺的是真内容和一层身份。", 30, WHITE, True, spacing=1.3)
txt(s, 0.9, 6.2, 8, 0.3, "文件与代码：D:\\Projects\\rc-ai-assistant", 11, RGBColor(0xFF, 0xD9, 0xDD))

prs.save(os.path.join(OUT, "CKLC资料库-进展-20261124.pptx"))
print("saved:", os.path.join(OUT, "CKLC资料库-进展-20261124.pptx"), len(prs.slides.__iter__.__self__._sldIdLst))
