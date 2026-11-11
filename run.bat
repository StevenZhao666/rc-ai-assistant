@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/2] 导入知识库...
".venv\Scripts\python.exe" scripts\ingest_xlsx.py "%~1"
echo [2/2] 启动服务：http://127.0.0.1:8001
".venv\Scripts\python.exe" -m uvicorn app.main:app --port 8001 --host 127.0.0.1
