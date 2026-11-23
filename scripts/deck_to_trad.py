"""把简体 PPT 转成繁体版：逐段替换文字，保留版式。

    python scripts/deck_to_trad.py docs/结构图-简.pptx docs/结构图-繁.pptx
"""
import sys
from pathlib import Path

from opencc import OpenCC
from pptx import Presentation

KEEP = [("崑崑", "崑崑"), ("崑崙", "崑崙")]


def conv(text: str, cc: OpenCC) -> str:
    # 吉祥物名字要先保护起来：OpenCC 会把「崑崑」误转成「崑崙」
    protected = text.replace("崑崑", "@@NAME@@").replace("崑崑", "@@NAME@@")
    out = cc.convert(protected).replace("@@NAME@@", "崑崑")
    for a, b in KEEP:          # 名字不做简化，保留山
        out = out.replace(a, b)
    return out


def walk(shapes):
    for sh in shapes:
        if sh.shape_type == 6:      # group
            yield from walk(sh.shapes)
            continue
        if getattr(sh, "has_table", False) and sh.has_table:
            for row in sh.table.rows:
                for cell in row.cells:
                    yield cell.text_frame
            continue
        if getattr(sh, "has_text_frame", False) and sh.has_text_frame:
            yield sh.text_frame


def main(src: str, dst: str) -> None:
    cc = OpenCC("s2t")
    prs = Presentation(src)
    n = 0
    for slide in prs.slides:
        for tf in walk(slide.shapes):
            for para in tf.paragraphs:
                for run in para.runs:
                    if run.text.strip():
                        run.text = conv(run.text, cc)
                        n += 1
    prs.save(dst)
    print(f"转换 {n} 段文字 → {dst}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/结构图-简.pptx",
         sys.argv[2] if len(sys.argv) > 2 else "docs/结构图-繁.pptx")
