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

echo Backend starting... http://127.0.0.1:8008
.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8008

endlocal
