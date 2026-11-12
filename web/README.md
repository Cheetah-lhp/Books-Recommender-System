# Books Recommender System

## Quick start

### Windows 

Run from Command Prompt:

```bat
copy .env.example .env
start.bat
```

Management commands:

```bat
start.bat status
start.bat logs
start.bat restart
start.bat stop
```

### Linux 

```bash
cp .env.example .env
chmod +x start.sh
./start.sh -d        
```

Management commands:

```bash
./start.sh status
./start.sh logs       # Ctrl+C exits logs only — containers keep running
./start.sh restart
./start.sh stop
```

### Access URLs

- **App (Windows / WSL2 with Host Proxy):** `http://127.0.0.1:3000` 
- **App (Linux / direct Nginx 1-origin):** `http://127.0.0.1:8090`
- **Backend API & Docs:** `http://127.0.0.1:8000` / `http://127.0.0.1:8000/docs`
- **Direct Ports:** Frontend container `:3001`, MySQL `:3307`, Redis `:6379`

## Notes

- Recommendation module runs at `web/backend/app/services/recommender.py`.
