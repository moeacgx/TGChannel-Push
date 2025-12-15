@echo off
chcp 65001 >nul
title 停止 TeChannel-Push

echo.
echo 正在停止 TeChannel-Push 服务...
echo.

:: 关闭后端 (uvicorn/python)
taskkill /F /FI "WINDOWTITLE eq TeChannel-Push Backend*" >nul 2>&1
taskkill /F /IM "python.exe" /FI "WINDOWTITLE eq TeChannel-Push*" >nul 2>&1

:: 关闭前端 (node/npm)
taskkill /F /FI "WINDOWTITLE eq TeChannel-Push Frontend*" >nul 2>&1

echo.
echo ✓ 服务已停止
echo.
pause
