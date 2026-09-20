@echo off
setlocal

cd /d %~dp0

if not exist .venv\Scripts\python.exe (
  echo Initializing Python environment...
  py -3 -m venv .venv
)

 .venv\Scripts\python.exe -c "import dotenv, uvicorn" >nul 2>&1
if errorlevel 1 (
  echo Backend dependencies are incomplete; installing requirements...
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Backend dependency installation failed.
    endlocal & exit /b 1
  )
)

echo V2 backend starting... http://127.0.0.1:8011
.venv\Scripts\python.exe run_local_backend_safe.py

endlocal
