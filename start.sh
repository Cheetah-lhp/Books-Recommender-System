#!/usr/bin/env bash
set -e

# Thu muc goc chua du an
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$ROOT_DIR/web"

echo "KHOI DONG BOOK RECOMMENDER SYSTEM"
echo ""

# Chon trinh thong dich Python
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

# Kich hoat virtualenv neu ton tai
if [ -d "$ROOT_DIR/venv" ]; then
    source "$ROOT_DIR/venv/bin/activate"
elif [ -d "$ROOT_DIR/.venv" ]; then
    source "$ROOT_DIR/.venv/bin/activate"
elif [ -d "$ROOT_DIR/web/backend/venv" ]; then
    source "$ROOT_DIR/web/backend/venv/bin/activate"
fi

echo "[1/4] Kiem tra Backend dependencies..."
cd backend
$PYTHON_CMD -m pip install -r requirements.txt -q

echo "[2/4] Kiem tra va khoi tao du lieu mau vao CSDL..."
$PYTHON_CMD init_sample_data.py
cd ..

echo "[3/4] Kiem tra Frontend dependencies..."
cd front_end
if [ ! -d "node_modules" ]; then
    echo "Dang cai dat thu vien Frontend qua npm..."
    npm install
fi
cd ..

echo "[4/4] Khoi chay he thong..."
echo "- Backend: http://127.0.0.1:8000"
echo "- Frontend: http://127.0.0.1:3000"
echo ""

# Khoi chay Backend
cd "$ROOT_DIR/web/backend"
$PYTHON_CMD -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# Khoi chay Frontend
cd "$ROOT_DIR/web/front_end"
npm run dev &
FRONTEND_PID=$!

# Don dep tien trinh khi dong chuong trinh
cleanup() {
    echo ""
    echo "Dang dung he thong..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Mo trinh duyet
sleep 3
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:3000 >/dev/null 2>&1 &
elif command -v open &> /dev/null; then
    open http://localhost:3000 >/dev/null 2>&1 &
fi

echo "He thong dang chay tren cong 3000. Nhan Ctrl+C de dung."
wait

