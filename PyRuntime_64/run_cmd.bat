@echo off
title Python Script Launcher
cls

:start
echo ============================================
echo      PYTHON SCRIPT LAUNCHER (INTERACTIVE)
echo ============================================
echo.

:: Input URL
set /p "target_url=Masukkan URL Services SheerID: "

:menu
echo.
echo Pilih Metode Koneksi:
echo [1]  Direct dengan email temporary (default)
echo [2]  Dengan proxy (ip:port)
echo [3]  Dengan proxy auth (user:pass)
echo [4]  Debug mode (no proxy)
echo [5]  Debug mode + proxy (ip:port)
echo [6]  Debug mode + proxy auth (user:pass)
echo [7]  Tanpa email temporary
echo [8]  Tanpa email temporary + proxy (ip:port)
echo [9]  Tanpa email temporary + proxy auth (user:pass)
echo [10] Email Manual
echo [11] Email Manual + proxy (ip:port)
echo [12] Email Manual + proxy auth (user:pass)
echo [13] Keluar
echo.

set /p "choice=Pilih nomor (1-13): "

if "%choice%"=="1" goto direct
if "%choice%"=="2" goto proxy_simple
if "%choice%"=="3" goto proxy_auth
if "%choice%"=="4" goto debug_mode
if "%choice%"=="5" goto debug_proxy
if "%choice%"=="6" goto debug_proxy_auth
if "%choice%"=="7" goto no_temp
if "%choice%"=="8" goto no_temp_proxy
if "%choice%"=="9" goto no_temp_proxy_auth
if "%choice%"=="10" goto email_manual
if "%choice%"=="11" goto email_manual_proxy
if "%choice%"=="12" goto email_manual_proxy_auth
if "%choice%"=="13" exit

echo Pilihan tidak valid, silakan coba lagi.
goto menu

:direct
echo Running: Direct Mode...
python.exe script.py "%target_url%"
pause
goto start

:proxy_simple
set /p "ip_port=Masukkan IP:Port (contoh 123.234.123.234:80): "
echo Running: Proxy Mode...
python.exe script.py --proxy %ip_port% "%target_url%"
pause
goto start

:proxy_auth
set /p "creds=Masukkan User:Pass (contoh admin:rahasia123): "
set /p "ip_port=Masukkan IP:Port (contoh 123.234.123.234:80): "
echo Running: Proxy Auth Mode...
python.exe script.py --proxy %creds%@%ip_port% "%target_url%"
pause
goto start

:debug_mode
echo Running: Debug Mode...
python.exe script.py --debug "%target_url%"
pause
goto start

:debug_proxy
set /p "ip_port=Masukkan IP:Port (contoh 123.234.123.234:80): "
echo Running: Debug Mode with Proxy...
python.exe script.py --debug --proxy %ip_port% "%target_url%"
pause
goto start

:debug_proxy_auth
set /p "creds=Masukkan User:Pass (contoh admin:rahasia123): "
set /p "ip_port=Masukkan IP:Port (contoh 123.234.123.234:80): "
echo Running: Debug Mode with Proxy Auth...
python.exe script.py --debug --proxy %creds%@%ip_port% "%target_url%"
pause
goto start

:no_temp
echo Running: No Temporary Email Mode...
python.exe script.py --no-temp-email "%target_url%"
pause
goto start

:no_temp_proxy
set /p "ip_port=Masukkan IP:Port (contoh 123.234.123.234:80): "
echo Running: No Temp Email + Proxy...
python.exe script.py --no-temp-email --proxy %ip_port% "%target_url%"
pause
goto start

:no_temp_proxy_auth
set /p "creds=Masukkan User:Pass (contoh admin:rahasia123): "
set /p "ip_port=Masukkan IP:Port (contoh 123.234.123.234:80): "
echo Running: No Temp Email + Proxy Auth...
python.exe script.py --no-temp-email --proxy %creds%@%ip_port% "%target_url%"
pause
goto start

:email_manual
set /p "user_email=Masukkan Email: "
echo Running: Email Manual Mode...
python.exe script.py "%target_url%" --email %user_email%
pause
goto start

:email_manual_proxy
set /p "user_email=Masukkan Email: "
set /p "ip_port=Masukkan IP:Port: "
echo Running: Email Manual + Proxy...
python.exe script.py "%target_url%" --email %user_email% --proxy %ip_port%
pause
goto start

:email_manual_proxy_auth
set /p "user_email=Masukkan Email: "
set /p "creds=Masukkan User:Pass: "
set /p "ip_port=Masukkan IP:Port: "
echo Running: Email Manual + Proxy Auth...
python.exe script.py "%target_url%" --email %user_email% --proxy %creds%@%ip_port%
pause
goto start