@echo off
setlocal
cd /d %~dp0

echo ===================================
echo   博维 AI 驾驶舱 V2 开发环境
echo ===================================

start "博维-V2后端" cmd /k ""%~dp0bowei_ai_dashboard\start-backend-dev.bat""
start "博维-V2前端" cmd /k ""%~dp0frontend-v2\start-frontend-v2-dev.bat""

timeout /t 6 /nobreak > nul
start "" "http://127.0.0.1:6005"

echo.
echo 已启动：
echo   后端：http://127.0.0.1:8011
echo   V2前端：http://127.0.0.1:6005
pause
endlocal
