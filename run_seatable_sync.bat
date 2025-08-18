@echo off
echo Starting SeaTable Sync Tool...
echo.

REM 设置编码为UTF-8
chcp 65001 > nul

REM 检查.env文件
if not exist .env (
    echo [INFO] .env file not found, creating from template...
    if exist .env.example (
        copy .env.example .env
        echo [INFO] Please edit .env file with your settings
        pause
    )
)

REM 运行程序
seatable-sync-windows.exe %*

REM 暂停以查看输出
if errorlevel 1 (
    echo.
    echo [ERROR] Program exited with error code: %errorlevel%
    echo.
    pause
)
