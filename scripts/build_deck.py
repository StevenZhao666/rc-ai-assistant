"""生成《崑崑 · 项目结构》演示文稿（简体，4 层）。

    ./.venv/Scripts/python.exe scripts/build_deck.py

输出：docs/结构图-简.pptx
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "结构图-简.pptx"

RED = RGBColor(0x88, 0x07, 0x0F)
INK = RGBColor(0x24, 0x1F, 0x20)
DIM = RGBColor(0x6F, 0x68, 0x64)
LINE = RGBColor(0xE2, 0xDB, 0xD6)
CREAM = RGBColor(0xFB, 0xF9, 0xF7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SOFT_RED = RGBColor(0xFD, 0xF4, 0xF3)
BLUE_BG = RGBColor(0xEF, 0xF5, 0xFC)
GREEN_BG = RGBColor(0xF0, 0xF8, 0xF3)
AMBER_BG = RGBColor(0xFF, 0xF7, 0xEA)
GRAY_BG = RGBColor(0xF4, 0xF1, 0xEF)
DARK_BG = RGBColor(0x6B, 0x05, 0x0C)

FONT = "Microsoft YaHei"
W, H = 13.333, 7.5


def new_deck() -> Presentation:
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    return prs


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def rect(slide, x, y, w, h, fill=None, line=None, radius=False, line_w=Pt(1)):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = line_w
    shape.shadow.inherit = False
    if radius:
        shape.adjustments[0] = 0.08
    shape.text_frame.text = ""
    return shape


def text(slide, x, y, w, h, s, size=14, color=INK, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.0):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    lines = s.split("\n")
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        r = p.add_run()
        r.text = ln
        r.font.name = FONT
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
    return box


def card(slide, x, y, w, h, title, sub="", fill=WHITE, border=LINE, tsize=13, ssize=10.5):
    rect(slide, x, y, w, h, fill=fill, line=border, radius=True)
    text(slide, x + 0.14, y + 0.1, w - 0.28, 0.3, title, size=tsize, bold=True)
    if sub:
        text(slide, x + 0.14, y + 0.42, w - 0.28, h - 0.48, sub, size=ssize, color=DIM, spacing=1.15)


def kicker(slide, s):
    text(slide, 0.62, 0.34, 6, 0.3, s, size=11, color=RED, bold=True)


def title(slide, s, size=28):
    text(slide, 0.6, 0.62, 12.1, 0.62, s, size=size, bold=True)


def bg(slide, color=CREAM):
    rect(slide, 0, 0, W, H, fill=color)


def down_arrow(slide, x, y, color=RGBColor(0xB9, 0xAE, 0xA8), label=""):
    shape = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(x), Inches(y), Inches(0.22), Inches(0.24))
    shape.fill.solid(); shape.fill.fore_color.rgb = color
    shape.line.fill.background(); shape.shadow.inherit = False
    if label:
        text(slide, x + 0.3, y, 3, 0.24, label, size=9.5, color=DIM)


def left_arrow(slide, x, y, w=0.5):
    shape = slide.shapes.add_shape(MSO_SHAPE.LEFT_ARROW, Inches(x), Inches(y), Inches(w), Inches(0.2))
    shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor(0xCF, 0xC5, 0xBE)
    shape.line.fill.background(); shape.shadow.inherit = False


def right_arrow(slide, x, y, w=0.5):
    shape = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(0.2))
    shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor(0xCF, 0xC5, 0xBE)
    shape.line.fill.background(); shape.shadow.inherit = False


# ── 第 1 页：封面 ────────────────────────────────────────
def slide_cover(prs):
    s = blank(prs)
    bg(s, RED)
    rect(s, 0, 5.4, W, 2.1, fill=DARK_BG)
    text(s, 0.9, 2.05, 11.5, 0.9, "崑崑 · 书院问答助手", size=44, color=WHITE, bold=True)
    text(s, 0.95, 3.05, 11, 0.5, "项目结构：从全景到数据库", size=20,
         color=RGBColor(0xFF, 0xD9, 0xD7))
    text(s, 0.95, 5.85, 11, 0.4, "张崑崙书院（CKLC） · 2026 年 11 月", size=12,
         color=RGBColor(0xF2, 0xC9, 0xC7))
    text(s, 0.95, 6.3, 11, 0.5,
         "四个层次：L0 全景 · L1 一次提问 · L2 数据库 · L3 未来设想", size=11,
         color=RGBColor(0xD9, 0xA9, 0xA6))


# ── 第 2 页：L0 全景 ─────────────────────────────────────
def slide_l0(prs):
    s = blank(prs)
    bg(s)
    kicker(s, "宏观 · L0")
    title(s, "一张图看全：谁在用 → 经过什么 → 数据在哪")
    text(s, 0.62, 1.28, 12, 0.3, "实线＝已经在跑；虚线＝设想。", size=10.5, color=DIM)

    bands = [
        ("使用者", 1.62, [("学生", "手机浏览器 · 繁简英", WHITE), ("审核人", "审批页 · 绑条款、发布", WHITE),
                          ("管理员", "后台 · 流水与成本", WHITE), ("外部系统", "别的项目 / 同学的 AI", GRAY_BG)]),
        ("服务（一台 2C4G，单进程 FastAPI）", 2.98,
         [("/api/ask", "限流 → 意图 → 检索 → 回答 → 溯源", SOFT_RED),
          ("/review", "队列 · 认领 · 绑条款 · 留痕", BLUE_BG),
          ("/admin", "8 个面板，只读", GREEN_BG),
          ("外部接口", "API / MCP（设想）", GRAY_BG)]),
        ("核心能力", 4.34,
         [("检索", "中文二元组 + BM25", WHITE), ("回答", "只依已发布条目 · 句末标 [n]", WHITE),
          ("溯源", "问答 → 条款 → 原文", WHITE), ("兜底", "实时 / 缺口 / 越界各有出口", WHITE)]),
        ("数据与外部", 5.62,
         [("SQLite", "6 张表", AMBER_BG), ("流水文件", "提问 · 用量", AMBER_BG),
          ("模型", "智谱 3 档 → DeepSeek 兜底", WHITE), ("官方资料", "规章 PDF · 房间规定", WHITE)]),
    ]

    for label, y, items in bands:
        text(s, 0.62, y, 6, 0.24, label, size=10, color=DIM, bold=True)
        cw, gap = 2.92, 0.14
        for i, (t, sub, fill) in enumerate(items):
            dash = fill == GRAY_BG
            card(s, 0.62 + i * (cw + gap), y + 0.28, cw, 0.72, t, sub,
                 fill=fill, border=LINE if not dash else RGBColor(0xC9, 0xBD, 0xB6), tsize=12, ssize=9.5)

    text(s, 0.62, 6.62, 12, 0.3,
         "L0 全景 → L1 放大「一次提问」→ L2 放大「数据库」→ L3 未来的库", size=10, color=DIM)


# ── 第 3 页：L1 八步 ────────────────────────────────────
def slide_l1(prs):
    s = blank(prs)
    bg(s)
    kicker(s, "微观 · L1")
    title(s, "一次提问走过的八步")
    text(s, 0.62, 1.28, 12, 0.3,
         "前三步判断该不该答；④ 判断要不要查；⑤⑥ 检索与生成；⑦⑧ 溯源与记账。", size=10.5, color=DIM)

    steps = [
        ("① 认身份", "学号 7 位" + chr(10) + "设备号", WHITE),
        ("② 安全", "代写 / 医疗" + chr(10) + "情绪 / 安全", SOFT_RED),
        ("③ 拦截", "天气 / 押金" + chr(10) + "门禁", SOFT_RED),
        ("④ 意图", "要不要" + chr(10) + "查资料", WHITE),
        ("⑤ 检索", "繁简归一" + chr(10) + "BM25", WHITE),
        ("⑥ 生成", "只给这几条" + chr(10) + "标 [n]", WHITE),
        ("⑦ 溯源", "只留真引用" + chr(10) + "漏标则兜底", WHITE),
        ("⑧ 记账", "模式 / 耗时" + chr(10) + "token", WHITE),
    ]

    cw, gap = 1.40, 0.11
    for i, (t, sub, fill) in enumerate(steps):
        x = 0.62 + i * (cw + gap)
        card(s, x, 1.86, cw, 1.34, t, sub, fill=fill, tsize=11.5, ssize=8.5)
        if i < len(steps) - 1:
            right_arrow(s, x + cw + 0.005, 1.86 + 0.6, 0.1)

    text(s, 0.62, 3.62, 6, 0.26, "三条岔路（不走主线）", size=10, color=DIM, bold=True)
    branches = [
        ("不查资料也能答", "打招呼、感谢、问「你是谁」" + chr(10) + "→ 模型直接回，不占额度。"),
        ("查了但没有", "直说查不到，给具体方向：" + chr(10) + "住宿 / 设施 / 流程，或转办公室。"),
        ("不该由机器答", "代写、医疗、情绪、人身安全、跨书院" + chr(10) + "→ 专用话术，不检索。"),
    ]
    bw, bgap = 3.94, 0.14
    for i, (t, sub) in enumerate(branches):
        x = 0.62 + i * (bw + bgap)
        rect(s, x, 3.95, bw, 1.75, fill=RGBColor(0xFC, 0xFA, 0xF9),
             line=RGBColor(0xD8, 0xCE, 0xC8), radius=True)
        text(s, x + 0.18, 4.1, bw - 0.36, 0.32, t, size=14, bold=True)
        text(s, x + 0.18, 4.52, bw - 0.36, 1.0, sub, size=10.5, color=DIM, spacing=1.25)

    text(s, 0.62, 6.62, 12, 0.3, "L1 请求流程　·　下一页：这些答案存在哪里（L2 数据库）", size=10, color=DIM)


# ── 第 4 页：L2 数据库 ──────────────────────────────────
def slide_l2(prs):
    s = blank(prs)
    bg(s)
    kicker(s, "微观 · L2")
    title(s, "数据库：问答与原文分开存")
    text(s, 0.62, 1.28, 12, 0.3,
         "一条知识＝一条可审核的断言；原文是另一层，只加不改。检索只吃 published 且未过期。",
         size=10.5, color=DIM)

    # 左表
    lx, ly, lw = 0.62, 1.75, 5.1
    rect(s, lx, ly, lw, 2.55, fill=WHITE, line=LINE, radius=True)
    rect(s, lx, ly, lw, 0.34, fill=GRAY_BG, line=LINE, radius=False)
    text(s, lx + 0.14, ly + 0.06, lw - 0.28, 0.26, "kb_item　问答层", size=12, bold=True)
    rows_l = [
        ("question / answer", "问题与答案"),
        ("status", "草稿 → 待审 → 发布 → 过期 → 归档"),
        ("ttl_type", "A 稳定 / B 年度 / C 实时"),
        ("source_url", "来源页面"),
        ("original_answer", "导入时原文"),
        ("source_chunk_id", "绑定的条款"),
    ]
    for i, (k, v) in enumerate(rows_l):
        yy = ly + 0.44 + i * 0.34
        text(s, lx + 0.16, yy, 1.55, 0.28, k, size=9, bold=True)
        text(s, lx + 1.74, yy, lw - 1.9, 0.28, v, size=9, color=DIM)

    # 中间箭头
    right_arrow(s, 5.86, ly + 1.1, 0.55)
    text(s, 5.72, ly + 1.36, 0.9, 0.5, "每条\n指向", size=8.5, color=DIM, align=PP_ALIGN.CENTER)

    # 右表
    rx, rw = 6.62, 6.1
    rect(s, rx, ly, rw, 2.55, fill=WHITE, line=LINE, radius=True)
    rect(s, rx, ly, rw, 0.34, fill=BLUE_BG, line=LINE, radius=False)
    text(s, rx + 0.14, ly + 0.06, rw - 0.28, 0.26, "chunk　原文层", size=12, bold=True)
    rows_r = [
        ("anchor", "条款号（3.2）"),
        ("section", "章节（Visitors）"),
        ("variant", "zh / en"),
        ("version", "AY2026-2027"),
        ("hash", "内容指纹，重导不重复"),
        ("text", "条款正文"),
    ]
    for i, (k, v) in enumerate(rows_r):
        yy = ly + 0.44 + i * 0.34
        text(s, rx + 0.16, yy, 1.3, 0.28, k, size=9, bold=True)
        text(s, rx + 1.5, yy, rw - 1.65, 0.28, v, size=9, color=DIM)

    # 下方四张记录表
    text(s, 0.62, 4.5, 6, 0.26, "行为记录（只追加，不改）", size=10, color=DIM, bold=True)
    logs = [
        ("qa_log", "谁、问什么、答什么\nmode · latency_ms\nn_cites"),
        ("feedback", "👍 / 👎\nnote 用户写的原因\nmode 当时模式"),
        ("review_log", "谁、何时、做了什么\naction（approve / bind）\nbefore / after"),
        ("candidate", "官网抓来的候选\nstatus 待处理\nitem_id 转正后"),
    ]
    cw2, gap2 = 2.92, 0.14
    for i, (t, sub) in enumerate(logs):
        x = 0.62 + i * (cw2 + gap2)
        rect(s, x, 4.82, cw2, 1.45, fill=AMBER_BG, line=RGBColor(0xEF, 0xDC, 0xB6), radius=True)
        text(s, x + 0.14, 4.9, cw2 - 0.28, 0.28, t, size=12, bold=True)
        text(s, x + 0.14, 5.22, cw2 - 0.28, 0.95, sub, size=9, color=DIM, spacing=1.2)

    text(s, 0.62, 6.62, 12, 0.3,
         "L2 数据库　·　下一页：如果要做成对外服务的书院数据库（L3）", size=10, color=DIM)


# ── 第 5 页：L3 未来 ────────────────────────────────────
def slide_l3(prs):
    s = blank(prs)
    bg(s)
    kicker(s, "设想 · L3")
    title(s, "如果做成书院数据库")
    text(s, 0.62, 1.28, 12, 0.3,
         "不只服务崑崑，还要给别的项目、同学的 AI 用。关键是分层与版本。", size=10.5, color=DIM)

    tiers = [
        ("① 原文层", "规章、通知、手册。带版本、生效与废止日期；" + chr(10) + "只加不改，历史可回溯。",
         "新增：doc · doc_version · clause"),
        ("② 知识层", "问答、术语表、常见误解。" + chr(10) + "每条指向原文层的一段，可审核、可撤回。",
         "新增：kb_item_ref · glossary"),
        ("③ 入口层", "API / MCP：谁能拿什么、配额多少；" + chr(10) + "每次调用留痕。",
         "新增：client · api_log"),
    ]
    cw, gap = 3.97, 0.18
    for i, (t, sub, new) in enumerate(tiers):
        x = 0.62 + i * (cw + gap)
        rect(s, x, 1.72, cw, 1.72, fill=RGBColor(0xFD, 0xFB, 0xFA), line=RGBColor(0xCB, 0xBF, 0xB8), radius=True)
        text(s, x + 0.18, 1.84, cw - 0.36, 0.3, t, size=14, bold=True)
        text(s, x + 0.18, 2.2, cw - 0.36, 0.8, sub, size=10, color=DIM, spacing=1.2)
        text(s, x + 0.18, 3.02, cw - 0.36, 0.3, new, size=9, color=RGBColor(0x9A, 0x5B, 0x00))

    text(s, 0.62, 3.66, 6, 0.26, "需要新增的表", size=10, color=DIM, bold=True)
    rows = [
        ("doc / doc_version", "现在版本信息散在 chunk 里，答不了“这条何时失效”“学生引的是哪一版”。"),
        ("clause", "把 chunk 兼任的职责拆开：文件 → 版本 → 条款。"),
        ("kb_item_ref", "一条问答可能靠两条条款；现在只能绑一条，还要标“直接规定 / 解释 / 参考”。"),
        ("client / api_log", "对外开放必须有身份、配额、审计；出事能追。"),
        ("glossary", "HA、RC、High Table 这类术语，现在只能靠条目凑。"),
    ]
    y0 = 3.98
    rect(s, 0.62, y0, 12.1, 0.3, fill=GRAY_BG, line=LINE, radius=False)
    text(s, 0.76, y0 + 0.04, 2.4, 0.24, "表", size=9, bold=True, color=DIM)
    text(s, 3.3, y0 + 0.04, 9, 0.24, "解决什么问题", size=9, bold=True, color=DIM)
    for i, (k, v) in enumerate(rows):
        yy = y0 + 0.3 + i * 0.42
        text(s, 0.76, yy + 0.05, 2.5, 0.3, k, size=9.5, bold=True)
        text(s, 3.3, yy + 0.05, 9.3, 0.34, v, size=9, color=DIM)
        rect(s, 0.62, yy + 0.4, 12.1, 0.008, fill=LINE)

    text(s, 0.62, 6.72, 12, 0.3,
         "对外只读接口先开四个：search_kb · get_item · get_clause · list_updates；MCP 就是包一层。",
         size=9.5, color=DIM)


def main() -> None:
    prs = new_deck()
    slide_cover(prs)
    slide_l0(prs)
    slide_l1(prs)
    slide_l2(prs)
    slide_l3(prs)
    prs.save(OUT)
    print("已生成", OUT, f"（{len(prs.slides.__iter__.__self__._sldIdLst)} 页）")


if __name__ == "__main__":
    main()
