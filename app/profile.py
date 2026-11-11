"""书院基础档案：这些事实太少、太常用，不适合只靠检索。

两个用途：
1. 生成知识库条目（可被引用、可被检索）
2. 拼成一段「常驻上下文」注入模型，保证基础问题永远答得上

来源全部来自书院官网，逐条标注 URL。改这里 = 改全站。
"""

SOURCE_HISTORY = "https://cklc.rc.um.edu.mo/college-history-layout/"
SOURCE_VISION = "https://cklc.rc.um.edu.mo/college-vision-and-mission/"
SOURCE_HOME = "https://cklc.rc.um.edu.mo/"

PROFILE = {
    "name": "张昆仑书院",
    "name_en": "Cheong Kun Lun College（CKLC）",
    "building": "W34",
    "location": "澳门大学横琴校区西南侧，靠近学生活动中心（SAC）与 University Mall",
    "address": "University of Macau, W34, Avenida da Universidade, Taipa, Macau",
    "founded": "2016 年（在横琴校区成立，是澳大十所住宿式书院中最新的一所；书院系统始于 2014 年）",
    "donor": "由 Cheong（张）家族捐资设立，以纪念澳门企业家、社区贡献者张昆仑先生",
    "rooms": "W34 大楼有 200 多间双人房，每间最多住 4 人（两个起居室，中间为卫浴）",
    "layout": "大楼呈 C 字形，四个转角各有楼梯与电梯；G 层为公共区域，包含书院办公室等",
    "office": "G 层 G003",
    "phone": "(+853) 8822 9520",
    "fax": "(+853) 8822 2381",
    "email": "cklcollege@um.edu.mo",
    "hours": "周一至周四 09:30-13:00 / 14:30-17:45；周五 09:30-13:00 / 14:30-17:30（法定节假日除外）",
    "spirit": "Be sunny（阳光健康）、Be honest（诚实守信）、Be cooperative（团队协作）、Be driven（自强不息）",
}

# 这些会变成知识库条目（问题, 答案, 来源名, 来源URL）
PROFILE_ENTRIES = [
    ("張崑崙書院在哪棟樓？", f"{PROFILE['name']}位于澳门大学 W34 楼，在横琴校区{PROFILE['location']}。", "书院历史与布局", SOURCE_HISTORY),
    ("書院什麼時候成立？", f"{PROFILE['founded']}。{PROFILE['donor']}。", "书院历史与布局", SOURCE_HISTORY),
    ("書院有多少房間和床位？", f"{PROFILE['rooms']}；{PROFILE['layout']}。", "书院历史与布局", SOURCE_HISTORY),
    ("書院是由誰捐資設立的？", f"{PROFILE['donor']}。", "书院历史与布局", SOURCE_HISTORY),
    ("書院的精神/使命是什麼？", f"書院以四個 Be 概括學生成長目標：{PROFILE['spirit']}。", "书院使命及愿景", SOURCE_VISION),
    ("書院的地址、電話和傳真是多少？", f"地址：{PROFILE['address']}；電話：{PROFILE['phone']}；傳真：{PROFILE['fax']}；電郵：{PROFILE['email']}。", "书院官网 · 联系方式", SOURCE_HOME),
]


def context_block() -> str:
    """注入模型的常驻档案（尽量短，只放基础事实）。"""
    return (
        f"【书院基础档案】\n"
        f"名称：{PROFILE['name']}（{PROFILE['name_en']}）\n"
        f"地址：{PROFILE['address']}（{PROFILE['building']} 楼，校园西南侧）\n"
        f"成立：{PROFILE['founded']}\n"
        f"规模：{PROFILE['rooms']}\n"
        f"办公室：{PROFILE['office']}｜电话 {PROFILE['phone']}｜电邮 {PROFILE['email']}\n"
        f"办公时间：{PROFILE['hours']}\n"
        f"精神：{PROFILE['spirit']}\n"
    )
