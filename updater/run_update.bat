@echo off
chcp 65001 >nul
title Portfolio 股票儀表板自動更新

echo.
echo ============================================
echo   Portfolio - 台美股儀表板自動更新
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] 抓取最新股價並更新 HTML...
python update_prices.py
if %errorlevel% neq 0 (
    echo.
    echo 更新失敗，請確認 Python 與套件已安裝
    echo pip install yfinance beautifulsoup4
    pause
    exit /b 1
)

echo.
echo [2/3] 同步 HTML 到 dashboard...
copy /y "portfolio_radar_v3.html" "..\dashboard\portfolio_radar_v3.html" >nul
echo    dashboard\portfolio_radar_v3.html 已更新

echo.
echo [3/3] 同步到 Google Drive...
set GDRIVE_PATH=C:\Users\%USERNAME%\Google Drive\Portfolio\dashboard
if exist "%GDRIVE_PATH%" (
    copy /y "portfolio_radar_v3.html" "%GDRIVE_PATH%\portfolio_radar_v3.html" >nul
    echo    已同步至 Google Drive
) else (
    echo    找不到 Google Drive 路徑，請編輯第 33 行 set GDRIVE_PATH
)

echo.
echo ============================================
echo   完成！手機開啟 Google Drive 即可查看
echo ============================================
echo.
timeout /t 5
