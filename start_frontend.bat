@echo off
cd /d "%~dp0frontend"
if not exist node_modules call npm install
echo Clinic frontend on http://localhost:5190
npm run dev
