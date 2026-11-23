@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === 冒烟：服务与页面 ===
.venv\Scripts\python.exe scripts\smoke.py
echo.
echo === MCP 四个工具 ===
.venv\Scripts\python.exe tests\test_mcp.py
echo.
echo === 自然语言查询（会调用一次模型） ===
.venv\Scripts\python.exe ask.py "書院能不能養寵物"
echo.
pause
