@echo off
chcp 65001 >nul
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" dingtalk_agent.py
  exit /b %ERRORLEVEL%
)
echo 请先执行: python -m venv .venv ^& .venv\Scripts\pip install -r requirements.txt
exit /b 1
