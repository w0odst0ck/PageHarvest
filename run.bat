@echo off
chcp 65001 >nul
title PageHarvest

echo ✦ PageHarvest 启动中...
echo.
echo   请在浏览器打开: http://localhost:8080
echo.
echo   按 Ctrl+C 停止
echo.

python -m web.app
pause
