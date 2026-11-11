"""全局配置。所有路径都从本文件推导，换机器不用改代码。"""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
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

# 每个书院只改这几行
COLLEGE_NAME = "张昆仑书院（CKLC）"
OFFICE_ROOM = "G 层 G003"
OFFICE_PHONE = "(+853) 8822 9520"
OFFICE_EMAIL = "cklcollege@um.edu.mo"
OFFICE_HOURS = "周一至周四 09:30-13:00 / 14:30-17:45，周五 09:30-13:00 / 14:30-17:30（法定节假日除外）"

# 模型：留空则用「抽取式」模式，不调模型也能跑
# 填了就是 OpenAI 兼容接口（校内 ICTO / 国内云 / 任何兼容服务都行）
LLM_BASE = os.environ.get("LLM_BASE", "").rstrip("/")
LLM_KEY = os.environ.get("LLM_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3.8-27b")

# 检索阈值：低于它就不答，走兜底卡片
MIN_SCORE = float(os.environ.get("MIN_SCORE", "2.5"))

# 当前学年：B 类（年度型）答案会带上这个前缀
ACADEMIC_YEAR = os.environ.get("ACADEMIC_YEAR", "2026/27")

# 审批人名单（学号或姓名，逗号分隔）。留空 = 不限制（本地开发用）
REVIEWERS = {x.strip() for x in os.environ.get("REVIEWERS", "").split(",") if x.strip()}
