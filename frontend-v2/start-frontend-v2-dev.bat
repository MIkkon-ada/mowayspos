@echo off
setlocal

cd /d %~dp0

if not exist node_modules\.bin\vite.cmd (
  npm install
  if errorlevel 1 (
    echo Frontend dependency installation failed.
    endlocal & exit /b 1
  )
)

npm run dev

endlocal
