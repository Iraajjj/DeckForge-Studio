@echo off
setlocal
cd /d "%~dp0"
echo.
echo ==============================================
echo       DeckForge Studio V4  --  Local QA
echo ==============================================
echo.
if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment ...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Trying python ...
    python -m venv .venv
  )
  if errorlevel 1 goto fail
)
if not exist ".venv\Scripts\python.exe" goto fail
echo Installing / checking local dependencies ...
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto fail
echo.
echo Starting DeckForge Studio ...
".venv\Scripts\python.exe" -m deckforge studio
if errorlevel 1 goto fail
exit /b 0
:fail
echo.
echo Could not start. Check Python is installed and available and that you are online for the first dependency install.
pause
exit /b 1
