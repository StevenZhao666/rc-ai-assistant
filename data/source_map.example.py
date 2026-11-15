"""来源映射（模板）。

复制成 data/source_map.py 再改。没有这个文件时，所有条目一律标成 unverified。

原则：
  能指到官方页面的就指页面；指不到就标 unverified，绝不编条款号。
  keys 从上往下匹配，先匹配先赢，所以把更具体的放前面。

type 取值：
  official   官方页面（书院/学校自己的）
  external   非官方但公开（学生自建站等，必须标警告）
  unverified 找不到来源，只能靠人工确认
"""

SOURCES = [
    {
        "keys": ("住宿", "房間", "房型", "宿位"),
        "name": "书院住宿（示例）",
        "url": "https://example.edu/college/accommodation",
        "type": "official",
    },
    {
        "keys": ("纪律", "處分", "扣分"),
        "name": "书院纪律规定（示例）",
        "url": "https://example.edu/college/discipline",
        "type": "official",
    },
    # 找不到官方页面时，宁可留空：
    # {
    #     "keys": ("押金",),
    #     "name": "未找到官方来源",
    #     "url": "",
    #     "type": "unverified",
    # },
]


def pick(question: str) -> dict:
    """给一条问题挑来源。找不到返回 unverified。"""
    for src in SOURCES:
        if any(k in question for k in src["keys"]):
            return {"url": src["url"], "title": src["name"], "type": src["type"]}
    return {"url": "", "title": "未指派来源", "type": "unverified"}
