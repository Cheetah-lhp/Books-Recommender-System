@echo off
chcp 65001 >nul
echo ========================================================
echo        KHOI DONG BOOK RECOMMENDER SYSTEM (READORA)
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/3] Kiem tra Backend dependencies...
cd backend
python -m pip install -r requirements.txt -q
cd ..

echo [2/3] Kiem tra Frontend dependencies...
cd front_end
if not exist node_modules (
    echo Dang cai dat thu vien Frontend qua npm...
    call npm install
)
cd ..

echo [3/3] Dang khoi chay he thong...
echo - Backend khoi chay tren http://127.0.0.1:8000
echo - Frontend khoi chay tren http://127.0.0.1:3000
echo.

start "Readora Backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"
start "Readora Frontend" cmd /k "cd /d "%~dp0front_end" && npm run dev"

timeout /t 3 >nul
start http://localhost:3000

echo ========================================================
echo   HE THONG DA DUOC MO TREN TRINH DUYET (PORT 3000)!
echo   De dung he thong, dong 2 cua so console vua bat len.
echo ========================================================
pause
