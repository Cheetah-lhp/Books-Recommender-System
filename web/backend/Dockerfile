FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Alembic best-effort, then seed catalog, then Gunicorn+Uvicorn workers
CMD ["sh", "-c", "alembic upgrade head || python -c \"from app.db.models import Base; from app.db.session import engine; Base.metadata.create_all(bind=engine)\" || true; python init_sample_data.py; exec gunicorn -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:${PORT:-8000} main:app"]
