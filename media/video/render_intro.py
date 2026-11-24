# -*- coding: utf-8 -*-
"""崑崑介绍片：1080x1920 / 30fps / 34s，纯 Pillow 逐帧。

两部分：01 結構（它怎麼答）· 02 效果（用起來長什麼樣）
底圖是 :8001 真實頁面的截圖，不是重画的假界面。
"""
import math, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
DUR = 34.0
N = int(DUR * FPS)

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "frames")
OUT_MP4 = os.path.join(HERE, "kunkun-intro-1080x1920.mp4")

F_R = r"C:\Windows\Fonts\msjh.ttc"      # 微軟正黑體
F_B = r"C:\Windows\Fonts\msjhbd.ttc"
F_M = r"C:\Windows\Fonts\consola.ttf"
F_MB = r"C:\Windows\Fonts\consolab.ttf"

BG = (250, 248, 245)
INK = (31, 23, 21)
INK2 = (78, 66, 62)
MUTED = (120, 106, 101)
ACCENT = (140, 18, 32)
LINE = (231, 224, 218)
WHITE = (255, 255, 255)

_fonts = {}


def F(path, size):
    k = (path, size)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(path, size, index=0)
    return _fonts[k]


def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def seg(t, a, b):
    if b <= a:
        return 1.0 if t >= b else 0.0
    return clamp((t - a) / (b - a))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = clamp(x)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def mix(c1, c2, t):
    t = clamp(t)
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


# ── 背景 ────────────────────────────────────────────────────────────
def background():
    im = Image.new("RGB", (W, H), BG)
    # 左上極淡酒紅（與頁面同一個色感）
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-W * 0.55, -H * 0.30, W * 0.85, H * 0.32], fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(180))
    tint = Image.new("RGB", (W, H), (140, 18, 32))
    im = Image.composite(tint, im, glow.point(lambda v: int(v * 0.16)))
    # 右下暖橙
    glow2 = Image.new("L", (W, H), 0)
    g2 = ImageDraw.Draw(glow2)
    g2.ellipse([W * 0.25, H * 0.74, W * 1.5, H * 1.3], fill=90)
    glow2 = glow2.filter(ImageFilter.GaussianBlur(200))
    tint2 = Image.new("RGB", (W, H), (200, 130, 80))
    im = Image.composite(tint2, im, glow2.point(lambda v: int(v * 0.10)))
    return im


BASE = background()


def new_canvas():
    return BASE.copy()


def txt(d, xy, s, font, fill, anchor="la"):
    d.text(xy, s, font=font, fill=fill, anchor=anchor)


def cn_track(d, xy, s, font, fill, track=2, center_x=None):
    """中文小標籤加字距（不能用 Consolas，會出豆腐塊）。"""
    widths = [d.textlength(ch, font=font) for ch in s]
    total = sum(widths) + track * (len(s) - 1)
    x = (center_x - total / 2) if center_x is not None else xy[0]
    y = xy[1]
    for ch, w in zip(s, widths):
        d.text((x, y), ch, font=font, fill=fill)
        x += w + track
    return total


def mono_track(d, xy, s, font, fill, track=6, anchor_center_x=None):
    """等寬字加字距；anchor_center_x 給定時整體居中。僅限 ASCII。"""
    widths = [d.textlength(ch, font=font) for ch in s]
    total = sum(widths) + track * (len(s) - 1)
    x = (anchor_center_x - total / 2) if anchor_center_x is not None else xy[0]
    y = xy[1]
    for ch, w in zip(s, widths):
        d.text((x, y), ch, font=font, fill=fill)
        x += w + track
    return total


def hairline(d, x1, y1, x2, y2, color, w=1):
    d.line([(x1, y1), (x2, y2)], fill=color, width=w)


# ── 手機外框 ────────────────────────────────────────────────────────
def load_shot(path, width):
    im = Image.open(path).convert("RGB")
    h = int(im.height * width / im.width)
    return im.resize((width, h), Image.LANCZOS)


HOME = load_shot(os.path.join(HERE, "ui-home.png"), 620)
CITE = load_shot(os.path.join(HERE, "ui-cite.png"), 900)


def phone(canvas, shot, cx, top, scr_w, radius=52, zoom=1.0, focus=0.5):
    """把截圖放進手機框；zoom>1 時以 focus(0=上 1=下) 為視窗中心裁切。"""
    d = ImageDraw.Draw(canvas)
    sw, sh = shot.size
    disp_h = int(scr_w * sh / sw)
    cw, ch = scr_w / zoom, disp_h / zoom
    x0 = (scr_w - cw) / 2
    y0 = clamp(disp_h * focus - ch / 2, 0, max(0, disp_h - ch))
    k = sw / scr_w
    box = (int(x0 * k), int(y0 * k), int((x0 + cw) * k), int((y0 + ch) * k))
    src = shot.crop(box).resize((scr_w, disp_h), Image.LANCZOS)
    vis_h = disp_h

    pad = 14
    bx0, by0 = cx - scr_w // 2 - pad, top - pad
    bx1, by1 = bx0 + scr_w + pad * 2, by0 + vis_h + pad * 2

    # 影子
    sh_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh_layer)
    sd.rounded_rectangle([bx0 + 10, by0 + 26, bx1 + 10, by1 + 30], radius=radius + 10,
                         fill=(60, 30, 28, 60))
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(26))
    canvas.paste(Image.alpha_composite(canvas.convert("RGBA"), sh_layer).convert("RGB"), (0, 0))

    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=radius + 8, fill=(255, 255, 255))
    d.rounded_rectangle([bx0 + 1, by0 + 1, bx1 - 1, by1 - 1], radius=radius + 7,
                        outline=(232, 226, 220), width=2)

    mask = Image.new("L", src.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, src.size[0], src.size[1]], radius=radius, fill=255)
    canvas.paste(src, (bx0 + pad, by0 + pad), mask)
    return {"bx0": bx0, "by0": by0, "bx1": bx1, "by1": by1,
            "pad": pad, "disp_h": disp_h, "y0": y0, "screen_h": vis_h}


# ── 段落 ────────────────────────────────────────────────────────────
def beat_opener(c, t, a, b):
    p = seg(t, a, b)
    if p <= 0 or p >= 1:
        return
    d = ImageDraw.Draw(c)
    mono_track(d, (100, 370), "CKLC  ·  KUN KUN  ·  MACAU", F(F_M, 21),
               mix(BG, MUTED, ease_out(seg(t, a, a + .5))), 3)

    # 大字
    k = ease_out(seg(t, a + .15, a + 1.0))
    if k > 0:
        ty = int(570 + (1 - k) * 90)
        d.text((96, ty), "崑崑", font=F(F_B, 300), fill=mix(BG, ACCENT, k))

    k2 = ease_out(seg(t, a + .55, a + 1.35))
    if k2 > 0:
        y = 980 + (1 - k2) * 40
        d.text((100, y), "張崑崙書院的 AI 助手", font=F(F_R, 52), fill=mix(BG, INK, k2))

    k3 = ease_out(seg(t, a + .85, a + 1.6))
    if k3 > 0:
        hairline(d, 100, 1090, 100 + int(560 * k3), 1090, mix(BG, LINE, 1))
        mono_track(d, (100, 1120), "159.75.225.125/ai", F(F_M, 30), mix(BG, INK2, k3), 1)

    k4 = ease_out(seg(t, a + 1.1, a + 1.85))
    if k4 > 0:
        d.text((100, 1215), "學生端 · 審批後台 · MCP 端點", font=F(F_R, 30), fill=mix(BG, MUTED, k4))

    k5 = ease_out(seg(t, a + 1.3, a + 1.95))
    if k5 > 0:
        hairline(d, 100, 1655, 100 + int(880 * k5), 1655, mix(BG, LINE, 1))
        d.text((100, 1692), "張崑崙書院 · 澳門大學 · 2026", font=F(F_R, 24), fill=mix(BG, MUTED, k5))


def beat_chapter(c, t, a, b, num, cn, en, sub):
    if t < a or t > b:
        return
    d = ImageDraw.Draw(c)
    k_in = ease_out(seg(t, a, a + .55))
    k_out = ease_out(seg(t, b - .5, b))
    y = int(H * (1 - k_in) + (-H * 0.12) * k_out)
    if y >= H:
        return
    d.rectangle([0, y, W, y + H], fill=ACCENT)
    # 細白線裝飾
    d.rectangle([0, y + 120, W, y + 122], fill=(255, 255, 255, 40))
    mono_track(d, (100, y + 300), num, F(F_MB, 150), (255, 255, 255), 6)
    d.text((100, y + 520), cn, font=F(F_B, 150), fill=WHITE)
    mono_track(d, (104, y + 760), en, F(F_M, 26), (255, 235, 232), 8)
    d.text((100, y + 840), sub, font=F(F_R, 34), fill=(252, 226, 224))
    d.rectangle([100, y + 1010, 100 + 120, y + 1014], fill=(255, 255, 255))


STEPS = [
    ("01", "學生端", "一頁 HTML，沒有框架、沒有打包"),
    ("02", "/api/ask", "學號 + 設備號，按小時限流"),
    ("03", "BM25 檢索", "117 條已發布資料，無向量庫"),
    ("04", "模型鏈", "glm-4.5-flash → deepseek-flash → 原文摘錄"),
    ("05", "答案 + 出處", "編號對齊引用卡，懸空標記自動刪"),
]


def beat_diagram(c, t, a, b):
    if t < a or t > b:
        return
    d = ImageDraw.Draw(c)
    k = ease_out(seg(t, a, a + .6))
    if k > 0:
        cn_track(d, (100, 210), "它怎麼答出一句有出處的話", F(F_R, 24), mix(BG, ACCENT, k), 2)

    top0, gap, ch, cw = 300, 268, 208, 880
    x0 = (W - cw) // 2
    for i, (idx, title, sub) in enumerate(STEPS):
        s = a + 1.0 + i * 0.62
        p = ease_out(seg(t, s, s + .55))
        if p <= 0:
            continue
        y = top0 + i * gap + (1 - p) * 26
        alpha = p
        d.rounded_rectangle([x0, y, x0 + cw, y + ch], radius=20,
                            fill=mix(BG, WHITE, alpha),
                            outline=mix(BG, LINE, alpha), width=2)
        mono_track(d, (x0 + 34, y + 30), idx, F(F_M, 20), mix(BG, ACCENT, alpha), 3)
        d.text((x0 + 34, y + 66), title, font=F(F_B, 46), fill=mix(BG, INK, alpha))
        d.text((x0 + 34, y + 132), sub, font=F(F_R, 26), fill=mix(BG, INK2, alpha))
        # 箭頭
        if i < len(STEPS) - 1:
            y1 = y + ch
            y2 = top0 + (i + 1) * gap
            pa = ease_out(seg(t, s + .3, s + .62))
            if pa > 0:
                mid = int(y1 + (y2 - y1) * pa)
                d.line([(W // 2, y1 + 4), (W // 2, mid)], fill=mix(BG, LINE, 1), width=3)
                if pa > .9:
                    d.polygon([(W // 2 - 9, mid - 2), (W // 2 + 9, mid - 2), (W // 2, mid + 12)],
                              fill=LINE)

    k2 = ease_out(seg(t, a + 4.6, a + 5.4))
    if k2 > 0:
        d.text((100, 1660), "2C4G 單進程 · 系統 Apache 反代 8091 · 資料未審核的一律不檢索",
               font=F(F_R, 26), fill=mix(BG, MUTED, k2))


def beat_phone_home(c, t, a, b):
    if t < a or t > b:
        return
    d = ImageDraw.Draw(c)
    p = ease_out(seg(t, a, a + .8))
    if p <= 0:
        return
    k = ease_out(seg(t, a + .1, a + .9))
    d.text((100, 150), "一個頁面，三個動作", font=F(F_B, 54), fill=mix(BG, INK, k))
    d.text((100, 236), "填學號 → 問 → 看依據", font=F(F_R, 30), fill=mix(BG, MUTED, k))

    top = int(330 + (1 - p) * 120)
    zoom = 1.0 + 0.03 * seg(t, a + .8, b)
    phone(c, HOME, W // 2, top, 620, zoom=zoom, focus=0.0)

    k2 = ease_out(seg(t, a + 1.5, a + 2.2))
    if k2 > 0:
        d = ImageDraw.Draw(c)
        d.text((100, 1706), "免責在最上面 · 學號決定額度 · 快捷問題一鍵問",
               font=F(F_R, 28), fill=mix(BG, ACCENT, k2))


def beat_phone_answer(c, t, a, b):
    """引用卡近景：整张卡按时长缓慢下移，读到「原文」为止。"""
    if t < a or t > b:
        return
    d = ImageDraw.Draw(c)
    p = ease_out(seg(t, a, a + .7))
    if p <= 0:
        return
    k = ease_out(seg(t, a + .05, a + .8))
    d.text((90, 120), "每一句，都能追到原文", font=F(F_B, 54), fill=mix(BG, INK, k))
    d.text((90, 206), "問：我想換房間，要點做？", font=F(F_R, 28), fill=mix(BG, MUTED, k))

    pw, ph, px, py = 900, 1300, 90, 360
    # 面板
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([px + 8, py + 22, px + pw + 8, py + ph + 26],
                                         radius=26, fill=(60, 30, 28, 55))
    sh = sh.filter(ImageFilter.GaussianBlur(22))
    c.paste(Image.alpha_composite(c.convert("RGBA"), sh).convert("RGB"), (0, 0))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle([px, py, px + pw, py + ph], radius=26, fill=WHITE,
                        outline=LINE, width=2)

    # 卡片內容：等比縮到 900 寬，再按進度上下平移
    scaled_h = int(CITE.size[1] * pw / CITE.size[0])
    max_pan = max(0, scaled_h - ph)
    pan = int(max_pan * ease_io(seg(t, a + .9, b - .2)))
    img = CITE.resize((pw, scaled_h), Image.LANCZOS).crop((0, pan, pw, pan + ph))
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw, ph], radius=24, fill=255)
    c.paste(img, (px, py), mask)

    d = ImageDraw.Draw(c)
    k3 = ease_out(seg(t, a + 1.2, a + 1.9))
    if k3 > 0:
        d.text((90, 1692), "條目編號 · 版本 · 核實日期 · 原文，四樣都在",
               font=F(F_R, 28), fill=mix(BG, ACCENT, k3))
    # 右側進度細線
    if max_pan:
        bar_h = int(ph * ph / scaled_h)
        prog = max_pan and (pan / max_pan)
        d.rounded_rectangle([px + pw - 10, py + 12, px + pw - 6, py + ph - 12], radius=4,
                            fill=(238, 232, 226))
        d.rounded_rectangle([px + pw - 10, py + 12 + int((ph - 24 - bar_h) * prog),
                             px + pw - 6, py + 12 + int((ph - 24 - bar_h) * prog) + bar_h],
                            radius=4, fill=(214, 196, 190))


NUMS = [("117", "條已發布資料"), ("3", "種語言"), ("10", "次／小時·每人"), ("0", "向量庫")]


def beat_numbers(c, t, a, b):
    if t < a or t > b:
        return
    d = ImageDraw.Draw(c)
    k = ease_out(seg(t, a, a + .5))
    cn_track(d, (100, 380), "規格", F(F_R, 24), mix(BG, ACCENT, k), 3)
    # 一條貫穿兩行的豎線
    kd = ease_out(seg(t, a + .2, a + .9))
    if kd > 0:
        d.line([(540, 470 - 10), (540, 470 - 10 + int(520 * kd))], fill=mix(BG, LINE, 1), width=1)
    for i, (num, label) in enumerate(NUMS):
        s = a + .2 + i * .28
        p = ease_out(seg(t, s, s + .55))
        if p <= 0:
            continue
        col = i % 2
        row = i // 2
        x = 100 + col * 470
        y = 470 + row * 320 + (1 - p) * 24
        d.text((x, y), num, font=F(F_B, 132), fill=mix(BG, ACCENT, p))
        d.text((x, y + 168), label, font=F(F_R, 28), fill=mix(BG, MUTED, p))
    hairline(d, 100, 1120, 980, 1120, mix(BG, LINE, ease_out(seg(t, a + 1.4, a + 2.0))))
    k2 = ease_out(seg(t, a + 1.5, a + 2.2))
    d.text((100, 1170), "沒有向量庫，也沒有 GPU。一台 2 核 4G 的雲主機就跑得動。",
           font=F(F_R, 32), fill=mix(BG, INK2, k2))


def beat_end(c, t, a, b):
    if t < a or t > b:
        return
    d = ImageDraw.Draw(c)
    p = ease_out(seg(t, a, a + .45))
    d.rectangle([0, 0, W, H], fill=mix(BG, ACCENT, p))
    k = ease_out(seg(t, a + .25, a + 1.0))
    if k > 0:
        d.text((100, 700), "問崑崑", font=F(F_B, 170), fill=mix(ACCENT, WHITE, k))
    k2 = ease_out(seg(t, a + .7, a + 1.4))
    if k2 > 0:
        mono_track(d, (104, 960), "159.75.225.125/ai", F(F_M, 34), mix(ACCENT, (255, 236, 234), k2), 2)
    k3 = ease_out(seg(t, a + 1.0, a + 1.7))
    if k3 > 0:
        d.text((100, 1090), "測試版 · 資料未審核 · 回答皆附出處", font=F(F_R, 28),
               fill=mix(ACCENT, (250, 214, 212), k3))
    # 收尾細線
    k4 = ease_out(seg(t, a + 1.2, b))
    if k4 > 0:
        d.rectangle([100, 1650, 100 + int(880 * k4), 1652], fill=(255, 255, 255))


BEATS = [
    (0.0, 2.6, beat_opener),
    (2.6, 4.8, lambda c, t, a, b: beat_chapter(c, t, a, b, "01", "結構", "STRUCTURE", "它怎麼答出一句有出處的話")),
    (4.8, 12.6, beat_diagram),
    (12.6, 14.8, lambda c, t, a, b: beat_chapter(c, t, a, b, "02", "效果", "RESULT", "學生實際看到的畫面")),
    (14.8, 21.0, beat_phone_home),
    (21.0, 27.6, beat_phone_answer),
    (27.6, 31.2, beat_numbers),
    (31.2, 34.0, beat_end),
]


def frame(t):
    c = new_canvas()
    for a, b, fn in BEATS:
        fn(c, t, a, b)
    # 進度條
    d = ImageDraw.Draw(c)
    d.rectangle([0, 0, int(W * clamp(t / DUR)), 3], fill=(140, 18, 32))
    return c


def main():
    os.makedirs(FRAMES, exist_ok=True)
    only = None
    if len(sys.argv) > 1:
        only = float(sys.argv[1])
    if only is not None:
        frame(only).save(os.path.join(HERE, "preview-%05.2f.png" % only))
        print("preview written for t=%.2f" % only)
        return
    for i in range(N):
        t = i / FPS
        frame(t).save(os.path.join(FRAMES, "%05d.png" % i))
        if i % 150 == 0:
            print("frame %d/%d" % (i, N), flush=True)
    print("done %d frames" % N)


if __name__ == "__main__":
    main()
