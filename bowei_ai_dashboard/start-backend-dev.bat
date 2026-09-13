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

echo Backend starting... http://127.0.0.1:8011
.venv\Scripts\python.exe -c "from pathlib import Path;import os;[os.environ.__setitem__(k.strip(),v) for line in Path('.env').read_text(encoding='utf-8').splitlines() if line.strip() and not line.lstrip().startswith('#') for k,v in [line.split('=',1)] if k.strip()];import uvicorn;uvicorn.run('app.main:app',host='0.0.0.0',port=8011,reload=True)"

endlocal
