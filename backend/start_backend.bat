@echo off
cd /d "%~dp0"
pip install -r requirements.txt --quiet
echo Clinic backend on http://localhost:8002
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8002
