@echo off
cd /d "%~dp0"
python -m uvicorn web.main:app --host 127.0.0.1 --port 8080 --reload
