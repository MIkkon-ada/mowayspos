@echo off
setlocal

cd /d %~dp0

if not exist .venv (
  echo Initializing Python environment...
  py -3 -m venv .venv
  call .venv\Scripts\activate
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)

echo V2 backend starting... http://127.0.0.1:8011
.venv\Scripts\python.exe run_local_backend_safe.py

endlocal
