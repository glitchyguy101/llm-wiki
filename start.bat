@echo off
echo.
echo  =============================================
echo    Wiki-LLM -- Gemini Agentic Wiki
echo  =============================================
echo.

:: Check for .env file
if not exist ".env" (
    echo  [!] .env file not found!
    echo  [*] Creating .env from template...
    copy .env.example .env >nul
    echo.
    echo  *** ACTION REQUIRED ***
    echo  Open .env and paste your Gemini API key:
    echo     GEMINI_API_KEY=your_key_here
    echo.
    echo  Get your key at: https://aistudio.google.com/apikey
    echo.
    pause
    start notepad .env
    exit /b
)

:: Install dependencies if needed
echo  [*] Checking dependencies...
pip show google-generativeai >nul 2>&1
if errorlevel 1 (
    echo  [*] Installing Python packages...
    pip install -r requirements.txt
    echo.
)

echo  [*] Starting Wiki-LLM server...
echo  [*] Open http://localhost:8000 in your browser
echo.
python agent/server.py
pause
