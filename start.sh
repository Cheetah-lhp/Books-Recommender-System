#!/usr/bin/env bash
set -e

# Thu muc goc chua du an
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$ROOT_DIR"

echo ""

# Phat hien WSL2 & Windows binaries
IS_WSL=0
if grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=1
fi

DOCKER_CMD="docker"
COMPOSE_CMD=()

# Kiem tra neu dang o WSL2 ma docker Linux chua ket noi daemon
if [ "$IS_WSL" -eq 1 ] && ! docker info >/dev/null 2>&1; then
    CANDIDATE_SOCKETS=(
        "/mnt/wsl/docker-desktop/shared-sockets/guest-services/docker.proxy.sock"
        "/mnt/wsl/docker-desktop/shared-sockets/guest-services/docker.sock"
        "/mnt/wsl/docker-desktop/docker-desktop-user-distro/docker.sock"
        "/mnt/wsl/docker-desktop/docker.sock"
        "$HOME/.docker/desktop/docker.sock"
    )
    for sock in "${CANDIDATE_SOCKETS[@]}"; do
        if [ -S "$sock" ] && [ -w "$sock" ]; then
            export DOCKER_HOST="unix://$sock"
            if docker info >/dev/null 2>&1; then
                echo "[start.sh] Da ket noi Docker qua Docker Desktop socket: $sock"
                break
            fi
        fi
    done
fi

# Neu van chua ket noi duoc daemon Linux, tu dong fallback sang Windows docker.exe
if [ "$IS_WSL" -eq 1 ] && ! docker info >/dev/null 2>&1; then
    WIN_DOCKER=""
    if [ -x "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe" ]; then
        WIN_DOCKER="/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
    elif command -v docker.exe >/dev/null 2>&1; then
        WIN_DOCKER="$(command -v docker.exe)"
    fi

    if [ -n "$WIN_DOCKER" ] && "$WIN_DOCKER" info < /dev/null >/dev/null 2>&1; then
        echo "[start.sh] Linux docker socket chua san sang; tu dong dung Docker Desktop ($WIN_DOCKER)."
        DOCKER_CMD="$WIN_DOCKER"
        COMPOSE_CMD=("$WIN_DOCKER" compose)
    fi
fi

if [ ${#COMPOSE_CMD[@]} -eq 0 ]; then
    if ! command -v "$DOCKER_CMD" >/dev/null 2>&1; then
        echo "Loi: Chua cai dat Docker."
        echo "Vui long cai Docker Engine hoac Docker Desktop truoc khi chay ./start.sh"
        exit 1
    fi

    if ! "$DOCKER_CMD" info >/dev/null 2>&1; then
        echo "Loi: Docker daemon chua chay hoac user hien tai chua co quyen truy cap Docker."
        if [ "$IS_WSL" -eq 1 ]; then
            echo "Goi y WSL2: Hay mo Docker Desktop tren Windows -> Settings -> Resources -> WSL Integration va bat toggle cho ban phan phoi WSL hien tai."
        else
            echo "Hay khoi dong Docker (vd: sudo systemctl start docker) va thu lai."
        fi
        exit 1
    fi

    if "$DOCKER_CMD" compose version >/dev/null 2>&1; then
        COMPOSE_CMD=("$DOCKER_CMD" compose)
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD=(docker-compose)
    else
        echo "Loi: Khong tim thay 'docker compose' hoac 'docker-compose'."
        echo "Vui long cai dat Docker Compose plugin (docker-compose-plugin)."
        exit 1
    fi
fi

# Tao file .env tu .env.example neu chua co
if [ ! -f "$ROOT_DIR/.env" ] && [ -f "$ROOT_DIR/.env.example" ]; then
    echo "[0/3] Chua thay file .env, dang tao tu .env.example..."
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

# Doc gia tri port tu .env (neu co)
read_env_var() {
    local key="$1"
    local default_val="$2"
    if [ -f "$ROOT_DIR/.env" ]; then
        local val
        val=$(grep -E "^${key}=" "$ROOT_DIR/.env" | tail -n 1 | cut -d '=' -f2- | tr -d '\r' | sed -E 's/^["'\'']|["'\'']$//g')
        if [ -n "$val" ]; then
            echo "$val"
            return
        fi
    fi
    echo "$default_val"
}

BACKEND_PORT="$(read_env_var BACKEND_PORT 8000)"
FRONTEND_PORT="$(read_env_var FRONTEND_PORT 3000)"
DOCKER_FRONTEND_PORT="$(read_env_var DOCKER_FRONTEND_PORT 3001)"
NGINX_PORT="$(read_env_var NGINX_PORT 8090)"

# Tim Windows node.exe
WIN_NODE=""
if [ "$IS_WSL" -eq 1 ]; then
    if [ -x "/mnt/c/Program Files/nodejs/node.exe" ]; then
        WIN_NODE="/mnt/c/Program Files/nodejs/node.exe"
    elif command -v node.exe >/dev/null 2>&1; then
        WIN_NODE="$(command -v node.exe)"
    fi
fi

PROXY_PID_FILE="$ROOT_DIR/web/.windows-host-proxy.pid"
PROXY_ACTIVE=0

stop_proxy() {
    if [ -f "$PROXY_PID_FILE" ]; then
        local pid
        pid=$(cat "$PROXY_PID_FILE" 2>/dev/null | tr -d '\r\n ')
        if [ -n "$pid" ]; then
            if [ "$IS_WSL" -eq 1 ] && command -v taskkill.exe >/dev/null 2>&1; then
                taskkill.exe /PID "$pid" /F < /dev/null >/dev/null 2>&1 || true
            else
                kill "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$PROXY_PID_FILE"
    fi
}

start_proxy() {
    if [ "$IS_WSL" -eq 1 ] && [ -n "$WIN_NODE" ] && [ -f "$ROOT_DIR/web/scripts/windows-host-proxy.js" ]; then
        # Neu proxy da dang lang nghe dung cong NGINX_PORT va hoat dong tot tren FRONTEND_PORT, giu nguyen
        if command -v curl >/dev/null 2>&1; then
            local health_json
            health_json=$(curl --connect-timeout 1 -m 2 -fsS "http://127.0.0.1:${FRONTEND_PORT}/__proxy_health" 2>/dev/null || true)
            if echo "$health_json" | grep -q "\"targetPort\":${NGINX_PORT}"; then
                PROXY_ACTIVE=1
                return 0
            fi
        fi
        stop_proxy
        local win_node
        win_node=$(wslpath -w "$WIN_NODE" 2>/dev/null || echo "node.exe")
        local win_script
        win_script=$(wslpath -w "$ROOT_DIR/web/scripts/windows-host-proxy.js" 2>/dev/null || echo "$ROOT_DIR/web/scripts/windows-host-proxy.js")
        local win_pid_file
        win_pid_file=$(wslpath -w "$PROXY_PID_FILE" 2>/dev/null || echo "$PROXY_PID_FILE")

        if command -v cmd.exe >/dev/null 2>&1; then
            cmd.exe /c start /b "" "$win_node" "$win_script" --port="$FRONTEND_PORT" --target="$NGINX_PORT" --pid-file="$win_pid_file" < /dev/null >/dev/null 2>&1 &
        else
            nohup "$WIN_NODE" "$win_script" --port="$FRONTEND_PORT" --target="$NGINX_PORT" --pid-file="$win_pid_file" < /dev/null >/dev/null 2>&1 &
        fi

        # Cho proxy san sang
        local proxy_ready=0
        for _ in $(seq 1 30); do
            if command -v curl >/dev/null 2>&1 && curl --connect-timeout 1 -m 2 -fsS "http://127.0.0.1:${FRONTEND_PORT}/__proxy_health" >/dev/null 2>&1; then
                proxy_ready=1
                PROXY_ACTIVE=1
                break
            fi
            sleep 0.1
        done
        if [ "$proxy_ready" -ne 1 ]; then
            echo "Canh bao: Windows Host Proxy khong the khoi dong hoac khong phan hoi tren cong ${FRONTEND_PORT}."
        fi
    fi
}

status_proxy() {
    if [ -f "$PROXY_PID_FILE" ]; then
        local pid
        pid=$(cat "$PROXY_PID_FILE" 2>/dev/null | tr -d '\r\n ')
        echo "Windows Host Proxy: Dang chay (PID: $pid, Port: $FRONTEND_PORT -> $NGINX_PORT via nginx)"
    else
        echo "Windows Host Proxy: Khong chay"
    fi
}

case "${1:-}" in
    stop|down)
        echo "Dang dung Windows Host Proxy..."
        stop_proxy
        echo "Dang dung cac container web..."
        "${COMPOSE_CMD[@]}" down < /dev/null
        exit 0
        ;;
    restart)
        echo "Dang dung he thong cu..."
        stop_proxy
        "${COMPOSE_CMD[@]}" down < /dev/null
        ;;
    logs)
        echo "Xem log backend va frontend (Nhan Ctrl+C de thoat log, cac container van tiep tuc chay):"
        trap 'echo -e "\nDa thoat xem log. Cac container van tiep tuc chay ngam."; exit 0' SIGINT SIGTERM
        "${COMPOSE_CMD[@]}" logs -f backend frontend < /dev/null
        exit 0
        ;;
    status)
        "${COMPOSE_CMD[@]}" ps < /dev/null
        status_proxy
        exit 0
        ;;
esac

FOLLOW_LOGS=0
if [ "${1:-}" = "-f" ] || [ "${1:-}" = "--follow" ] || [ "${1:-}" = "-l" ] || [ "${1:-}" = "--logs" ]; then
    FOLLOW_LOGS=1
fi

echo "[1/3] Build va khoi chay MySQL, Redis, Backend, Frontend, Nginx qua Docker..."
if "${COMPOSE_CMD[@]}" up --help < /dev/null 2>/dev/null | grep -q -- '--wait'; then
    "${COMPOSE_CMD[@]}" up -d --build --wait mysql redis backend frontend nginx < /dev/null
else
    "${COMPOSE_CMD[@]}" up -d --build mysql redis backend frontend nginx < /dev/null
    echo "Dang cho cac service san sang..."
    READY=0
    for _ in $(seq 1 90); do
        if command -v curl >/dev/null 2>&1 \
            && curl --connect-timeout 2 -m 5 -fsS "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1 \
            && curl --connect-timeout 2 -m 5 -fsS "http://127.0.0.1:${NGINX_PORT}/health" >/dev/null 2>&1 \
            && curl --connect-timeout 2 -m 5 -fsS "http://127.0.0.1:${DOCKER_FRONTEND_PORT}/" >/dev/null 2>&1; then
            READY=1
            break
        fi
        sleep 2
    done
    if [ "$READY" -ne 1 ]; then
        echo "Canh bao: Qua thoi gian cho service san sang. Kiem tra log: ${COMPOSE_CMD[*]} logs"
    fi
fi

# Khoi dong Windows Host Proxy duoi WSL2 de dam bao Windows Browser khong bi socket stall
if [ "$IS_WSL" -eq 1 ]; then
    start_proxy
fi

echo "[2/3] He thong da san sang:"
if [ "$PROXY_ACTIVE" -eq 1 ]; then
    FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"
    echo "- App (Proxy -> Nginx): http://127.0.0.1:${FRONTEND_PORT} (-> :${NGINX_PORT})"
else
    FRONTEND_URL="http://127.0.0.1:${NGINX_PORT}"
    echo "- App (Nginx 1-origin): http://127.0.0.1:${NGINX_PORT}"
fi
echo "- Nginx (direct):       http://127.0.0.1:${NGINX_PORT}"
echo "- Frontend (direct):    http://127.0.0.1:${DOCKER_FRONTEND_PORT} (container)"
echo "- Backend:              http://127.0.0.1:${BACKEND_PORT}"
echo "- API Docs:             http://127.0.0.1:${BACKEND_PORT}/docs"
echo ""

# Mo trinh duyet (uu tien 127.0.0.1 de tranh delay IPv6 ::1 tren mot so may Windows/WSL2)
echo "[3/3] Dang mo trinh duyet..."
if [ "$IS_WSL" -eq 1 ] && command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c start "" "$FRONTEND_URL" < /dev/null >/dev/null 2>&1 &
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$FRONTEND_URL" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
    open "$FRONTEND_URL" >/dev/null 2>&1 &
fi

echo "Cac container dang chay ngam trong Docker."
echo "- Xem log:       ${COMPOSE_CMD[*]} logs -f backend frontend (hoac ./start.sh logs)"
echo "- Kiem tra:      ./start.sh status"
echo "- Dung he thong: ./start.sh stop (hoac ${COMPOSE_CMD[*]} down)"

if [ "$FOLLOW_LOGS" -eq 1 ]; then
    echo ""
    echo "Dang xem log (Nhan Ctrl+C de thoat log - cac container van tiep tuc chay ngam):"
    trap 'echo -e "\nDa thoat xem log. Cac container van tiep tuc chay ngam."; exit 0' SIGINT SIGTERM
    "${COMPOSE_CMD[@]}" logs -f backend frontend < /dev/null
fi
