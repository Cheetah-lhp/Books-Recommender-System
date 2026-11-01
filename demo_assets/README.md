# Portable demo model

This folder contains the small serving-only snapshot of `remote-demo`: sparse
TF-IDF item vectors, ALS item factors, work/edition aliases and model parameters.
It lets a fresh checkout run the real hybrid model without Java, Spark or training.

Run from the repository root:

```bash
python scripts/setup_demo.py --install
```

The script validates and unpacks the archive into ignored `artifacts/remote-demo/`.
The SQLite catalog is created separately from the already tracked `samples_data/`.
No raw Goodreads download, local database, logs, checkpoints, training interactions
or full Spark model directory is included in this archive. The versioned demo
asset is intentional; newly trained runs remain ignored under `artifacts/`.

`manifest.json` records archive and per-file SHA-256 hashes. The snapshot contains
9,914 works, was trained with ALS rank 16 / 5 iterations and is for demonstrating
the pipeline; it is not a claim of evaluated recommendation quality.

For maintainers, `python scripts/setup_demo.py --package` builds these files from
an existing `artifacts/remote-demo/serving/` run. It refuses to replace an existing
archive; version changes should be deliberate and reviewed along with the manifest.
