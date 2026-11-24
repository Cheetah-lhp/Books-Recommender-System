FROM python:3.11-slim

ARG INSTALL_TRAIN=0

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && if [ "$INSTALL_TRAIN" = "1" ]; then \
         apt-get install -y --no-install-recommends openjdk-21-jre-headless; \
       fi \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

WORKDIR /app
COPY pyproject.toml README.md ./
COPY model/books_recommender ./model/books_recommender
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ "$INSTALL_TRAIN" = "1" ]; then \
      python -c "import subprocess,sys,tomllib; p=tomllib.load(open('pyproject.toml','rb'))['project']; subprocess.check_call([sys.executable,'-m','pip','install',*p['dependencies'],*p['optional-dependencies']['train'],*p['optional-dependencies']['serve']])"; \
    else \
      python -c "import subprocess,sys,tomllib; p=tomllib.load(open('pyproject.toml','rb'))['project']; subprocess.check_call([sys.executable,'-m','pip','install',*p['dependencies'],*p['optional-dependencies']['serve']])"; \
    fi \
    && pip install --no-deps .
COPY scripts/setup_demo.py ./scripts/setup_demo.py
COPY model/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
