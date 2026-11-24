#!/bin/sh
set -eu

cd /app
python scripts/setup_demo.py
exec books-recommender serve --run-id remote-demo --host 0.0.0.0 --port 8001
