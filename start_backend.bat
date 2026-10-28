@echo off
cd /d "%~dp0neurogut-backend"
.venv\Scripts\python.exe -m uvicorn main:app --port 8000
