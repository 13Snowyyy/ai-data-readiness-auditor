@echo off
REM ==========================================================
REM  AI Data Readiness Auditor - one-click launcher (Windows)
REM  Creates a virtual environment, installs dependencies,
REM  and starts the Streamlit app.
REM ==========================================================

cd /d "%~dp0"

echo.
echo === AI Data Readiness Auditor ===
echo.

REM Create a virtual environment on first run.
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Is Python installed and on PATH?
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call ".venv\Scripts\activate.bat"

echo Installing / updating dependencies...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt

echo.
echo Starting the app in your browser...
echo (Press CTRL+C in this window to stop the app.)
echo.
python -m streamlit run app.py

pause
