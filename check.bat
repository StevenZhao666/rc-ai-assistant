@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === 冒烟：服务与页面 ===
.venv\Scripts\python.exe scripts\smoke.py
echo.
echo === MCP 四个工具 ===
.venv\Scripts\python.exe tests\test_mcp.py
echo.
echo === 内容版本契约 ===
.venv\Scripts\python.exe tests	est_versions.py
echo.
echo === 评测基线（30 条） ===
set SCRAPE_BYPASS=local-eval
.venv\Scripts\python.exe scripts\eval_set.py --ask-none
echo.
echo === 文件接口 ===
.venv\Scripts\python.exe tests	est_files.py
echo.
echo === 反扒（会用到假 IP，约 60 次请求） ===
.venv\Scripts\python.exe tests	est_scrape.py
echo.
echo === cklc-files MCP ===
.venv\Scripts\python.exe tests	est_mcp_files.py
echo.
echo === 自然语言查询（会调用一次模型） ===
.venv\Scripts\python.exe ask.py "書院能不能養寵物"
echo.
pause
