@echo off
rem Starts the Next.js dev server (PORT env var if set, else 3000).
cd /d "%~dp0neurogut-frontend"
if "%PORT%"=="" set PORT=3000
npm run dev -- --port %PORT%
