@echo off
setlocal
cd /d %~dp0

if not exist .venv\Scripts\python.exe (
  echo Python virtual environment is missing. Run start-backend-dev.bat once first.
  exit /b 1
)

echo Starting local backend at http://127.0.0.1:8009
echo Loading .env credentials and using this project's SQLite database.
.venv\Scripts\python.exe -c "from pathlib import Path; import os; from dotenv import load_dotenv; load_dotenv('.env', override=True); os.environ['DATABASE_URL'] = 'sqlite:///' + (Path.cwd() / 'bowei_ai_dashboard.db').resolve().as_posix(); import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', port=8009)"

endlocal
