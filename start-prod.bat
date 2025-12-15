@echo off
chcp 65001 >nul
title TeChannel-Push 生产模式

echo.
echo  ╔════════════════════════════════════════════╗
echo  ║     TeChannel-Push 生产模式启动            ║
echo  ║     (前端构建 + 后端服务)                  ║
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

:: 构建前端
echo [1/2] 正在构建前端...
cd web
call npm run build
if errorlevel 1 (
    echo [错误] 前端构建失败！
    pause
    exit /b 1
)
cd ..
echo       ✓ 前端构建完成
echo.

:: 启动后端
echo [2/2] 正在启动后端服务...
echo.
echo  ╔════════════════════════════════════════════╗
echo  ║  ✓ 启动完成！                              ║
echo  ║                                            ║
echo  ║  访问地址:  http://localhost:8000          ║
echo  ║  API 文档:  http://localhost:8000/docs     ║
echo  ║                                            ║
echo  ║  按 Ctrl+C 停止服务                        ║
echo  ╚════════════════════════════════════════════╝
echo.

:: 打开浏览器
start http://localhost:8000

:: 激活虚拟环境并启动
call .venv\Scripts\activate.bat
python -m techannel_push
