@echo off
setlocal
cd /d %~dp0

echo ===================================
echo   博维 AI 驾驶舱 - 启动开发环境
echo ===================================

start "博维-后端" cmd /k ""%~dp0bowei_ai_dashboard\start-backend-dev.bat""
start "博维-前端" cmd /k ""%~dp0frontend\start-frontend-dev.bat""

echo 等待服务启动...
timeout /t 6 /nobreak > nul

start "" "http://127.0.0.1:6001"

echo.
echo 已启动：
echo   后端：http://127.0.0.1:8008
echo   前端：http://127.0.0.1:6001
echo.
echo 关闭此窗口不会影响服务运行。
pause
endlocal
