"""多语言模板：兜底、拒答、链接卡都要跟着提问语言走。

为什么单独抽出来：
- 英文用户拿到中文模板 = 完全不可用（测试里 22 次请求有 4 次返回中文）
- 粤语/繁体用户拿到简体模板 = 很割裂
- 这些文案不调模型，没法靠提示词解决，只能在这里出三套

语言判定用最省事的启发式：
  拉丁字母占比 > 汉字 → en
  含粤语特有字/繁体字 → zh-Hant
  其余 → zh-Hans
"""
import re

_CC = "唔嘅喺咗冇佢哋睇嘢邊點閂噉咁啲攞搵嚟"
_HANT = "書院房間證復讓與為這個們學會東發實現點麼樣辦規則圖書館"
_LATIN = re.compile(r"[A-Za-z]")
_HAN = re.compile(r"[\u4e00-\u9fff]")


def detect_lang(text: str) -> str:
    t = text or ""
    latin = len(_LATIN.findall(t))
    han = len(_HAN.findall(t))
    if latin > han and latin >= 3:
        return "en"
    if any(ch in t for ch in _CC) or sum(1 for ch in t if ch in _HANT) >= 2:
        return "zh-Hant"
    return "zh-Hans"


def office_line(lang: str) -> str:
    from . import config
    if lang == "en":
        return ("College Office: G/F, Room G003 | (+853) 8822 9520 | cklcollege@um.edu.mo\n"
                "Office hours: Mon–Thu 09:30–13:00 & 14:30–17:45; Fri 09:30–13:00 & 14:30–17:30")
    if lang == "zh-Hant":
        return (f"書院辦公室：{config.OFFICE_ROOM}｜{config.OFFICE_PHONE}｜{config.OFFICE_EMAIL}\n"
                f"辦公時間：{config.OFFICE_HOURS}")
    return (f"书院办公室：{config.OFFICE_ROOM}｜{config.OFFICE_PHONE}｜{config.OFFICE_EMAIL}\n"
            f"办公时间：{config.OFFICE_HOURS}")


def office_brief(lang: str) -> str:
    from . import config
    if lang == "en":
        return f"College Office G003 · {config.OFFICE_PHONE} · {config.OFFICE_EMAIL}"
    if lang == "zh-Hant":
        return f"書院辦公室 G003 · {config.OFFICE_PHONE} · {config.OFFICE_EMAIL}"
    return f"书院办公室 G003 · {config.OFFICE_PHONE} · {config.OFFICE_EMAIL}"


def fallback(lang: str) -> str:
    if lang == "en":
        return ("I don't have this one in the college materials, and I'd rather not guess.\n"
                "Try rephrasing, or ask the office: " + office_brief(lang))
    if lang == "zh-Hant":
        return ("這條書院資料裡沒有，我不敢亂講。\n"
                "換個說法再問我一次，或者直接問辦公室：" + office_brief(lang))
    return ("这条书院资料里没有，我不敢乱讲。\n"
            "换个说法再问，或者直接问办公室：" + office_brief(lang))


def meta_identity(lang: str) -> str:
    """身份题：一句范围 + 一个追问。不列能力清单、不列禁区清单（那才是客服味）。"""
    if lang == "en":
        return "I help CKLC residents look things up: rooms, facilities, hall rules, forms. What do you need?"
    if lang == "zh-Hant":
        return "我主要幫院生查 CKLC 嘅資料：房務、設施、院規、辦事流程都可以問。你想查邊樣？"
    return "我主要帮院生查 CKLC 的资料：房务、设施、院规、办事流程都能问。你想查哪件？"


def fallback_live(lang: str, channel: str) -> str:
    """实时/校外信息：给对的口子，不要甩书院办公室。"""
    if lang == "en":
        return "I cannot look up live information like that. Check " + channel + "."
    if lang == "zh-Hant":
        return "呢類實時資訊我查唔到，要睇" + channel + "。"
    return "这类实时信息我查不到，得看" + channel + "。"


def fallback_gap(lang: str, topic: str) -> str:
    """已知的资料缺口：直接承认没有，给下一步，不猜。"""
    if lang == "en":
        return ("The materials do not cover " + topic +
                ". Ask the college office (G003, 8822 9520) and they can confirm.")
    if lang == "zh-Hant":
        return topic + "，現有資料冇寫。要辦就直接問 G003：（+853）8822 9520。"
    return topic + "，现有资料没写。要办就直接问 G003：（+853）8822 9520。"


def fallback_low(lang: str) -> str:
    """检索没命中，但问题在范围内：请对方说具体点，不责怪、不甩电话。"""
    if lang == "en":
        return ("I did not find a matching entry. Can you be more specific: "
                "is it about your room, a facility, or a procedure?")
    if lang == "zh-Hant":
        return "搵唔到對應嘅條目。你可唔可以講具體啲：係問房間、設施，定係辦事流程？"
    return "没找到对应条目。你能说具体点吗：是问房间、设施，还是办事流程？"


def college_intro(lang: str) -> str:
    """「书院介绍」这类泛问题：直接用基础档案讲，不要检索。"""
    from .profile import PROFILE
    b = PROFILE["building"]
    room = PROFILE["office"].replace("G 层 ", "")
    if lang == "en":
        return (f"{PROFILE['name_en']} is one of the ten residential colleges at the University of Macau. "
                f"It was founded in 2016 on the Hengqin campus, sits in Building {b}, "
                f"and was endowed by the Cheong family.\n"
                f"The building has over 200 twin rooms (up to 4 students each); the ground floor "
                f"holds the common areas and the college office ({room}).\n"
                "Its student-development motto is four Be: sunny, honest, cooperative, driven.")
    if lang == "zh-Hant":
        return (f"{PROFILE['name']}（CKLC）是澳大十所住宿式書院之一，"
                "2016 年在橫琴校區成立，位於 " + b + " 樓，由張氏家族捐資設立。\n"
                "大樓有 200 多間雙人房，每間最多住 4 人；G 層是公共空間與書院辦公室（" + room + "）。\n"
                "書院以四個 Be 概括學生成長目標：" + PROFILE["spirit"] + "。")
    return (f"{PROFILE['name']}（CKLC）是澳大十所住宿式书院之一，"
            "2016 年在横琴校区成立，位于 " + b + " 楼，由张氏家族捐资设立。\n"
            "大楼有 200 多间双人房，每间最多住 4 人；G 层是公共空间和书院办公室（" + room + "）。\n"
            "书院用四个 Be 概括学生成长目标：" + PROFILE["spirit"] + "。")


def link_only(lang: str, url: str) -> str:
    if lang == "en":
        return ("This kind of information changes quickly (events, notices, deadlines), "
                "so I won't paraphrase it — here is the official page:\n" + url)
    if lang == "zh-Hant":
        return "這類資訊變動很快（活動、通知、截止日期），我不做轉述，只給入口：\n" + url
    return "这类信息变动很快（活动、通知、截止日期），我不做转述，只给入口：\n" + url


def out_of_scope(lang: str) -> str:
    if lang == "en":
        return ("I only hold materials for Cheong Kun Lun College (CKLC). Rules at other colleges may differ, "
                "so I won't apply ours to them.\nSee the RC system site: https://rc.um.edu.mo/")
    if lang == "zh-Hant":
        return ("我只收錄了張崑崙書院（CKLC）的資料，其他書院的規定可能不一樣，不能拿本院的答案套過去。\n"
                "建議查看澳大書院系統總站：https://rc.um.edu.mo/")
    return ("我只收录了张昆仑书院（CKLC）的资料，其他书院的规定可能不一样，不能拿本院的答案套过去。\n"
            "建议查看澳大书院系统总站：https://rc.um.edu.mo/")


def policy(kind: str, lang: str) -> str:
    """kind: academic / wellbeing / safety / emergency / medical"""
    if lang == "en":
        table = {
            "academic": ("I don't write assignments or essays for students — that's academic misconduct under "
                         "university rules.\nI can explain the rules, point you to the right form, or refer you to "
                         "study support (Library, RC Academic Tutorial, CTLE writing support)."),
            "wellbeing": ("This isn't something a Q&A bot should handle, but here is where to get a real person:\n"
                          "· College office / resident social worker: " + office_line(lang) +
                          "\n· Student Affairs Office (SAO) counselling service\n"
                          "If you are in immediate danger, call 999 (Macau emergency) or contact the college security."),
            "safety": ("For anything involving personal safety or property, please go to a real person:\n"
                       "· Emergency: 999 (Macau)\n· College security / office: " + office_line(lang) +
                       "\n· For theft, also file a police report.\nI don't give legal or medical advice."),
            "emergency": ("**Emergency — call now: 999 (Macau: police / fire / ambulance).**\n"
                          "Then notify the college security desk and the college office so they can let responders in.\n"
                          + office_line(lang)),
            "medical": ("I can't give medical advice, medicine names or dosages.\n"
                        "Please see a doctor: campus health centre, or the nearest hospital emergency department "
                        "if symptoms are severe. For emergencies call 999."),
        }
        return table[kind]
    if lang == "zh-Hant":
        table = {
            "academic": ("代寫作業或論文我不做——這屬於學術不端，書院和學校都有明確規定。\n"
                         "我可以幫的：解釋規章原文、告訴你表格在哪、指路到學習支援（圖書館、RC Academic Tutorial、CTLE 寫作支援）。"),
            "wellbeing": ("這類事情不適合由問答機器人處理，但可以說清楚去哪裡找人：\n"
                          "· 書院辦公室／駐院社工：" + office_line(lang) + "\n"
                          "· 學生事務部（SAO）有輔導服務\n"
                          "如當下有緊急危險，請立刻撥 999（澳門緊急電話），或聯絡書院保安。"),
            "safety": ("涉及人身或財物安全的情況，請直接找真人：\n"
                       "· 緊急：999（澳門）\n· 書院保安／辦公室：" + office_line(lang) +
                       "\n· 財物失竊建議同時報警並通知書院辦公室備案。\n我不提供法律或醫療建議。"),
            "emergency": ("**緊急情況，請立即致電 999（澳門：警察／消防／救護車）。**\n"
                          "然後通知書院保安及書院辦公室，方便他們開門引導救援人員。\n" + office_line(lang)),
            "medical": ("我不能提供醫療建議、藥名或劑量。\n"
                        "請盡快就醫：校內醫療中心，或症狀嚴重時到最近的醫院急診。緊急情況請撥 999。"),
        }
        return table[kind]
    table = {
        "academic": ("这类我不做：代写作业或论文属于学术不端，书院和学校对此有明确规定。\n"
                     "我可以帮的：解释规章原文、告诉你表格在哪、指路到学习支援（图书馆、RC Academic Tutorial、CTLE 的写作支持）。"),
        "wellbeing": ("这类事情不适合由问答机器人处理，但可以说清楚去哪找人：\n"
                      "· 书院办公室／驻院社工：" + office_line(lang) + "\n"
                      "· 学生事务部（SAO）有辅导服务\n"
                      "如果当下有紧急危险，请立刻拨 999（澳门紧急电话），或联系书院保安。"),
        "safety": ("这类涉及人身或财物安全的情况，请直接找真人处理：\n"
                   "· 紧急：999（澳门）\n· 书院保安／办公室：" + office_line(lang) +
                   "\n· 财物失窃建议同时报警并通知书院办公室备案。\n我不提供法律或医疗建议。"),
        "emergency": ("**紧急情况，请立即拨打 999（澳门：警察／消防／救护车）。**\n"
                      "然后通知书院保安和书院办公室，方便他们开门引导救援人员。\n" + office_line(lang)),
        "medical": ("我不能提供医疗建议、药名或剂量。\n"
                    "请尽快就医：校内医疗中心，或症状严重时到最近的医院急诊。紧急情况请拨 999。"),
    }
    return table[kind]
