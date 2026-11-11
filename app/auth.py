"""身份认证：本地开发用 mock，上线换成「复用 PHP session」。

这是整个项目里唯一需要改动的「接缝」。业务代码只认 current_user，
不关心这张票是 cookie、header 还是 OIDC 发出来的。

上线时的替换方式（方案 §4.1）：
    cookie: PHPSESSID=<id>
      → 内网请求 http://127.0.0.1/whoami.php（带上同一个 cookie）
      → {"student_id": "UC593618", "name": "..."}
      → 变成下面这个 User
"""
from dataclasses import dataclass

from fastapi import Header


@dataclass
class User:
    student_id: str
    name: str = ""
    college: str = "CKLC"
    source: str = "mock"


def get_current_user(x_student_id: str | None = Header(default=None)) -> User:
    """本地开发：从请求头 X-Student-Id 取；没有就用默认测试账号。

    这样前端可以先跑起来，不用等 HTTPS / 域名 / 反代全部打通。
    """
    return User(student_id=x_student_id or "UC000000", name="本地测试用户", source="mock")
