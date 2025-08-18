@echo off
echo Starting SeaTable Sync Tool...
echo.

REM ���ñ���ΪUTF-8
chcp 65001 > nul

REM ���.env�ļ�
if not exist .env (
    echo [INFO] .env file not found, creating from template...
    if exist .env.example (
        copy .env.example .env
        echo [INFO] Please edit .env file with your settings
        pause
    )
)

REM ���г���
seatable-sync-windows.exe %*

REM ��ͣ�Բ鿴���
if errorlevel 1 (
    echo.
    echo [ERROR] Program exited with error code: %errorlevel%
    echo.
    pause
)
