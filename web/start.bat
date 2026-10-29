@echo off
chcp 65001 >nul
echo KHOI DONG BOOK RECOMMENDER SYSTEM
echo.

cd /d "%~dp0"

echo [1/4] Kiem tra Backend dependencies...
cd backend
python -m pip install -r requirements.txt -q

echo [2/4] Kiem tra va khoi tao du lieu mau vao CSDL...
python init_sample_data.py
cd ..

echo [3/4] Kiem tra Frontend dependencies...
cd front_end
if not exist node_modules (
    echo Dang cai dat thu vien Frontend qua npm...
    call npm install
)
cd ..

echo [4/4] Khoi chay he thong...
echo - Backend: http://127.0.0.1:8000
echo - Frontend: http://127.0.0.1:3000
echo.

start "Readora Backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"
start "Readora Frontend" cmd /k "cd /d "%~dp0front_end" && npm run dev"

timeout /t 3 >nul
start http://localhost:3000

echo He thong da khoi dong tren trinh duyet (port 3000).
echo De dung he thong, vui long dong 2 cua so console.
pause
