@echo off
:: Freakuency — WinDivert Driver Cleanup
:: Run this (as Administrator) if the app crashed and you can't delete
:: the Freakuency folder because WinDivert64.sys is locked.

echo ============================================
echo   Freakuency - WinDivert Driver Cleanup
echo ============================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click and select "Run as administrator".
    echo.
    pause
    exit /b 1
)

echo Stopping WinDivert driver services...
sc stop WinDivert >nul 2>&1
sc stop WinDivert1.3 >nul 2>&1
sc stop WinDivert14 >nul 2>&1
sc stop WinDivert1.4 >nul 2>&1

echo Removing WinDivert driver services...
sc delete WinDivert >nul 2>&1
sc delete WinDivert1.3 >nul 2>&1
sc delete WinDivert14 >nul 2>&1
sc delete WinDivert1.4 >nul 2>&1

echo.
echo Done! The WinDivert driver has been unloaded.
echo You should now be able to delete the Freakuency folder.
echo.
echo If the file is still locked, try restarting your PC.
echo.
pause
