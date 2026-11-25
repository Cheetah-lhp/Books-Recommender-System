FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y default-jre && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY process.py process_samples.py process_enriched.py process_samples_enriched.py book_enrichment.py build_ol_lookup.py ./

CMD ["python", "-u", "process.py"]