"""全局配置。所有路径都从本文件推导，换机器不用改代码。"""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR") or (ROOT / "data"))
DB_PATH = DATA_DIR / "kb.sqlite3"
STATIC_DIR = ROOT / "app" / "static"


def _load_dotenv() -> None:
    """极简 .env 读取：不引入依赖，已存在的环境变量优先。"""
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

# 每个书院只改这几行（也可以用环境变量覆盖，见 .env.example）
COLLEGE_NAME = os.environ.get("COLLEGE_NAME", "张昆仑书院（CKLC）")
OFFICE_ROOM = os.environ.get("OFFICE_ROOM", "G 层 G003")
OFFICE_PHONE = os.environ.get("OFFICE_PHONE", "(+853) 8822 9520")
OFFICE_EMAIL = os.environ.get("OFFICE_EMAIL", "cklcollege@um.edu.mo")
OFFICE_HOURS = "周一至周四 09:30-13:00 / 14:30-17:45，周五 09:30-13:00 / 14:30-17:30（法定节假日除外）"

# 模型：留空则用「抽取式」模式，不调模型也能跑
# 填了就是 OpenAI 兼容接口（校内 ICTO / 国内云 / 任何兼容服务都行）
LLM_BASE = os.environ.get("LLM_BASE", "").rstrip("/")
LLM_KEY = os.environ.get("LLM_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3.8-27b")
# 推理型模型（如 deepseek-flash）默认会先想一大段，短回答会被 max_tokens 截成空串。
# 默认关掉思考；要开就 LLM_THINKING=on。带 thinking 参数被供应商拒绝时会自动去掉重试。
LLM_THINKING = os.environ.get("LLM_THINKING", "off").strip().lower() in ("on", "1", "true", "yes")

# 供应商链：主 → 同供应商备用模型（免费档常报「访问量过大」）→ 另一家兜底。
# 任何一环成功就返回；全挂才退回抽取式。
LLM_FALLBACK_MODELS = [x.strip() for x in os.environ.get("LLM_FALLBACK_MODELS", "").split(",") if x.strip()]
LLM_FB_BASE = os.environ.get("LLM_FALLBACK_BASE", "").rstrip("/")
LLM_FB_KEY = os.environ.get("LLM_FALLBACK_KEY", "")
LLM_FB_MODEL = os.environ.get("LLM_FALLBACK_MODEL", "")

# 主供应商的并发上限（智谱免费档 = 1）。0 表示不限。排不上队就换下一环。
LLM_CONCURRENCY = int(os.environ.get("LLM_CONCURRENCY", "1"))
LLM_QUEUE_WAIT = float(os.environ.get("LLM_QUEUE_WAIT", "4"))
# 单次请求硬上限：免费档偶尔直接挂住不返回（实测有 120s 的），别让它拖死线程
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "45"))

LLM_CHAIN: list[dict] = []
if LLM_BASE and LLM_KEY:
    lim = LLM_CONCURRENCY or None
    LLM_CHAIN.append({"base": LLM_BASE, "key": LLM_KEY, "model": LLM_MODEL, "limit": lim})
    for m in LLM_FALLBACK_MODELS:
        LLM_CHAIN.append({"base": LLM_BASE, "key": LLM_KEY, "model": m, "limit": lim})
if LLM_FB_BASE and LLM_FB_KEY and LLM_FB_MODEL:
    LLM_CHAIN.append({"base": LLM_FB_BASE, "key": LLM_FB_KEY, "model": LLM_FB_MODEL})

# 检索阈值：低于它就不答，走兜底卡片
MIN_SCORE = float(os.environ.get("MIN_SCORE", "2.5"))

# 当前学年：B 类（年度型）答案会带上这个前缀
ACADEMIC_YEAR = os.environ.get("ACADEMIC_YEAR", "2026/27")

# 审批人名单（学号或姓名，逗号分隔）。留空 = 不限制（本地开发用）
REVIEWERS = {x.strip() for x in os.environ.get("REVIEWERS", "").split(",") if x.strip()}

# 管理员名单（能看数据看板、能看完整学号）。留空 = 与 REVIEWERS 相同
ADMINS = {x.strip() for x in os.environ.get("ADMINS", "").split(",") if x.strip()}
