@echo off
chcp 65001 >nul
title CKLC AI 助手 - 启动
cd /d "%~dp0.."

echo ============================================
echo   张昆仑书院 AI 助手 - 启动
echo ============================================
echo.
echo [1/4] 清理旧进程...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
taskkill /F /IM cloudflared.exe >nul 2>&1
ping -n 3 127.0.0.1 >nul

rem 每次启动先备份数据库，避免误删/误操作丢库
if not exist backups mkdir backups
if exist data\kb.sqlite3 powershell -NoProfile -Command "Copy-Item 'data\kb.sqlite3' ('backups\kb-' + (Get-Date -Format 'yyyyMMdd-HHmm') + '.sqlite3')" >nul 2>&1

echo [2/4] 启动后端 (0.0.0.0:8001)...
powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath '.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','app.main:app','--port','8001','--host','0.0.0.0' -RedirectStandardOutput 'data\server.out' -RedirectStandardError 'data\server.err'" >nul 2>&1
ping -n 9 127.0.0.1 >nul

echo [3/4] 健康检查...
curl -s -m 5 --noproxy "*" http://127.0.0.1:8001/health
echo.

echo [4/4] 启动公网隧道（自动跳过打不开的域名）...
".venv\Scripts\python.exe" scripts\restart_tunnel.py 4

".venv\Scripts\python.exe" scripts\show_urls.py
echo.
echo   关掉本窗口不影响服务。要停服务跑 scripts\stop_all.bat
echo ============================================
if not "%1"=="/nopause" pause
