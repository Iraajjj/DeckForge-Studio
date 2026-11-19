@echo off
setlocal
cd /d "%~dp0"
echo.
echo ==============================================
echo          DeckForge Studio V4 Demo
echo ==============================================
echo.
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
  if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto fail
if not exist "demo_project\deckforge.json" (
  ".venv\Scripts\python.exe" -m deckforge demo demo_project
  if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -m deckforge build demo_project
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m deckforge verify demo_project\build\deckforge_package.zip
if errorlevel 1 goto fail
echo.
echo Opening the interactive HTML dashboard ...
start "" "demo_project\build\qa_dashboard.html"
echo SUCCESS. All materials are also in demo_project\build\.
pause
exit /b 0
:fail
echo Unable to run demo; check Python and dependency installation.
pause
exit /b 1
