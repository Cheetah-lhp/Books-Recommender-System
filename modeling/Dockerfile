FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip python -c \
    "import subprocess,sys,tomllib; p=tomllib.load(open('pyproject.toml','rb'))['project']; subprocess.check_call([sys.executable,'-m','pip','install',*p['dependencies'],*p['optional-dependencies']['train'],*p['optional-dependencies']['serve']])"
COPY src ./src
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-deps .

ENTRYPOINT ["books-recommender"]
