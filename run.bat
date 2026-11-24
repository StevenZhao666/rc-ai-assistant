@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%~1"=="" goto serve
echo [1/2] 导入知识库：%~1
".venv\Scripts\python.exe" scripts\build_kb.py "%~1"
if errorlevel 1 (
  echo 导入失败，先不启动服务。
  pause
  exit /b 1
)

:serve
echo [2/2] 启动服务：http://127.0.0.1:8001
".venv\Scripts\python.exe" -m uvicorn app.main:app --port 8001 --host 127.0.0.1
