@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.

if /i "%~1"=="stop" goto do_stop
if /i "%~1"=="down" goto do_stop
if /i "%~1"=="restart" goto do_restart
if /i "%~1"=="logs" goto do_logs
if /i "%~1"=="status" goto do_status

:check_docker
where docker >nul 2>&1
if errorlevel 1 (
    echo Loi: Chua cai dat Docker Desktop.
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo Loi: Docker Desktop chua duoc khoi dong. Hay mo Docker Desktop va thu lai.
    pause
    exit /b 1
)

if not exist ".env" (
    if exist ".env.example" (
        echo [0/3] Chua thay file .env, dang tao tu .env.example...
        copy /Y ".env.example" ".env" >nul
    )
)

set "FRONTEND_PORT=3000"
set "BACKEND_PORT=8000"
set "DOCKER_FRONTEND_PORT=3001"
set "NGINX_PORT=8090"
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if "%%A"=="FRONTEND_PORT" if not "%%B"=="" set "FRONTEND_PORT=%%B"
        if "%%A"=="BACKEND_PORT" if not "%%B"=="" set "BACKEND_PORT=%%B"
        if "%%A"=="DOCKER_FRONTEND_PORT" if not "%%B"=="" set "DOCKER_FRONTEND_PORT=%%B"
        if "%%A"=="NGINX_PORT" if not "%%B"=="" set "NGINX_PORT=%%B"
    )
)

rem Sanitize quotation marks and whitespace
set "FRONTEND_PORT=%FRONTEND_PORT:"=%"
set "BACKEND_PORT=%BACKEND_PORT:"=%"
set "DOCKER_FRONTEND_PORT=%DOCKER_FRONTEND_PORT:"=%"
set "NGINX_PORT=%NGINX_PORT:"=%"
set "FRONTEND_PORT=%FRONTEND_PORT:'=%"
set "BACKEND_PORT=%BACKEND_PORT:'=%"
set "DOCKER_FRONTEND_PORT=%DOCKER_FRONTEND_PORT:'=%"
set "NGINX_PORT=%NGINX_PORT:'=%"
for /f "tokens=* delims= " %%i in ("%FRONTEND_PORT%") do set "FRONTEND_PORT=%%i"
for /f "tokens=* delims= " %%i in ("%BACKEND_PORT%") do set "BACKEND_PORT=%%i"
for /f "tokens=* delims= " %%i in ("%DOCKER_FRONTEND_PORT%") do set "DOCKER_FRONTEND_PORT=%%i"
for /f "tokens=* delims= " %%i in ("%NGINX_PORT%") do set "NGINX_PORT=%%i"

echo [1/3] Build va khoi chay MySQL, Redis, Backend, Frontend, Nginx qua Docker...
docker compose up -d --build --wait mysql redis backend frontend nginx
if errorlevel 1 (
    echo Loi khi khoi chay Docker Compose.
    pause
    exit /b 1
)

set "APP_URL=http://127.0.0.1:%NGINX_PORT%"
where node >nul 2>&1
if not errorlevel 1 (
    if exist "web\scripts\windows-host-proxy.js" (
        if exist "web\.windows-host-proxy.pid" (
            for /f "usebackq" %%p in ("web\.windows-host-proxy.pid") do taskkill /PID %%p /F >nul 2>&1
            del /f /q "web\.windows-host-proxy.pid" >nul 2>&1
        )
        start /b "" node web\scripts\windows-host-proxy.js --port=%FRONTEND_PORT% --target=%NGINX_PORT% --pid-file="web\.windows-host-proxy.pid" <nul >nul 2>&1
        set "APP_URL=http://127.0.0.1:%FRONTEND_PORT%"
    )
)

echo [2/3] He thong da san sang:
echo - App:      %APP_URL% ^(Nginx 1-origin: http://127.0.0.1:%NGINX_PORT%^)
echo - Backend:  http://127.0.0.1:%BACKEND_PORT%
echo - API Docs: http://127.0.0.1:%BACKEND_PORT%/docs
echo.

echo [3/3] Dang mo trinh duyet...
start "" "%APP_URL%"

echo Cac container dang chay ngam trong Docker.
echo - Xem log:       docker compose logs -f backend frontend (hoac start.bat logs)
echo - Kiem tra:      start.bat status
echo - Dung he thong: start.bat stop (hoac docker compose down)
pause
exit /b 0

:do_stop
echo Dang dung Windows Host Proxy...
if exist "web\.windows-host-proxy.pid" (
    for /f "usebackq" %%p in ("web\.windows-host-proxy.pid") do taskkill /PID %%p /F >nul 2>&1
    del /f /q "web\.windows-host-proxy.pid" >nul 2>&1
)
echo Dang dung cac container web...
docker compose down
exit /b 0

:do_logs
echo Xem log backend va frontend (Nhan Ctrl+C de thoat log):
docker compose logs -f backend frontend
exit /b 0

:do_status
docker compose ps
if exist "web\.windows-host-proxy.pid" (
    echo Windows Host Proxy: Dang chay
) else (
    echo Windows Host Proxy: Khong chay
)
exit /b 0

:do_restart
echo Dang dung he thong cu...
if exist "web\.windows-host-proxy.pid" (
    for /f "usebackq" %%p in ("web\.windows-host-proxy.pid") do taskkill /PID %%p /F >nul 2>&1
    del /f /q "web\.windows-host-proxy.pid" >nul 2>&1
)
docker compose down
goto check_docker
