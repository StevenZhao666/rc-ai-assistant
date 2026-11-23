@echo off
chcp 65001 >nul
cd /d "%~dp0"
:loop
set "q="
set /p q=问书院（直接关窗口退出）: 
if not defined q goto :eof
.venv\Scripts\python.exe ask.py "%q%"
echo.
goto loop
