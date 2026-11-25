@echo off
setlocal
set "PYTHONUTF8=1"
set "DEEPSIGHT_PY=%~dp0..\.venv\Scripts\python.exe"
if exist "%DEEPSIGHT_PY%" (
  "%DEEPSIGHT_PY%" "%~dp0burn_deepsight_hud.py" %*
) else (
  python "%~dp0burn_deepsight_hud.py" %*
)
