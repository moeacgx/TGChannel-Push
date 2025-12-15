@echo off
chcp 65001 >nul
title TeChannel-Push 开发环境

echo.
echo  ╔════════════════════════════════════════════╗
echo  ║     TeChannel-Push 一键启动脚本            ║
echo  ║     Telegram 多频道广告置顶机器人          ║
echo  ╚════════════════════════════════════════════╝
echo.

:: 获取脚本所在目录
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

:: 检查虚拟环境
if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 未找到虚拟环境 .venv
    echo 请先运行: python -m venv .venv
    pause
    exit /b 1
)

:: 检查 node_modules
if not exist "web\node_modules" (
    echo [提示] 前端依赖未安装，正在安装...
    cd web
    call npm install
    cd ..
    echo.
)

echo [1/2] 正在启动后端服务...
echo       API 地址: http://localhost:8000
echo       Swagger:  http://localhost:8000/docs
echo.

:: 启动后端（新窗口）
start "TeChannel-Push Backend" cmd /k "cd /d "%PROJECT_DIR%" && call .venv\Scripts\activate.bat && python -m techannel_push"

:: 等待后端启动
echo [等待] 后端启动中...
timeout /t 3 /nobreak >nul

echo [2/2] 正在启动前端开发服务器...
echo       前端地址: http://localhost:3000
echo.

:: 启动前端（新窗口）
start "TeChannel-Push Frontend" cmd /k "cd /d "%PROJECT_DIR%\web" && npm run dev"

:: 等待前端启动
timeout /t 3 /nobreak >nul

echo.
echo  ╔════════════════════════════════════════════╗
echo  ║  ✓ 启动完成！                              ║
echo  ║                                            ║
echo  ║  后端 API:  http://localhost:8000          ║
echo  ║  前端面板:  http://localhost:3000          ║
echo  ║  API 文档:  http://localhost:8000/docs     ║
echo  ║                                            ║
echo  ║  关闭服务: 直接关闭对应的命令行窗口        ║
echo  ╚════════════════════════════════════════════╝
echo.

:: 自动打开浏览器
echo 正在打开浏览器...
timeout /t 2 /nobreak >nul
start http://localhost:3000

echo.
echo 此窗口可以关闭，不影响服务运行。
pause
