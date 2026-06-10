@echo off
setlocal enabledelayedexpansion
echo ======================================
echo  Gemini Audiobook Generator Setup 
echo ======================================
if not exist .env (
    copy .env.example .env > nul
    echo [ERROR] PLEASE EDIT the .env file and add your GEMINI_API_KEY before running again.
    pause
    exit /b 1
)
if not exist venv\ (
    python -m venv venv
)
call venv\Scriptsctivate.bat
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
python main.py %*
echo [SUCCESS] Execution completed!
pause