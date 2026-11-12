@echo off
chcp 65001 >nul
title CKLC AI 助手 · 停止
echo 停止后端与隧道...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)
taskkill /F /IM cloudflared.exe >nul 2>&1
echo 已停止。
timeout /t 2 >nul
