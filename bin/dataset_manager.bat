@echo off
set "DIST_ROOT=%~dp0.."
cd /d "%DIST_ROOT%"
python src\run_dataset_manager.py
if errorlevel 1 echo Install Python 3.9+ and optionally: pip install -r requirements.txt
pause
