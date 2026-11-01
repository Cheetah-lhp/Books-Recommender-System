from pathlib import Path

import pytest

from books_recommender.config import load_config
from books_recommender.data.prepare import validate_raw_files


def test_sample_config_resolves_paths():
    config = load_config(Path("configs/sample.yaml"))
    assert config["mode"] == "sample"
    assert Path(config["paths"]["raw"]).is_absolute()
    assert config["models"]["hybrid"]["als_weight"] == 0.70


def test_invalid_hybrid_weights(tmp_path):
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(
        "models:\n  hybrid:\n    als_weight: 1\n    content_weight: 1\n    popularity_weight: 1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="weights must sum"):
        load_config(config_path)


def test_missing_raw_files_fail_before_spark_starts(tmp_path):
    config = load_config(Path("configs/sample.yaml"))
    config["paths"]["raw"] = str(tmp_path)
    with pytest.raises(FileNotFoundError, match="goodreads_books.json") as error:
        validate_raw_files(config)
    assert "process/download.ipynb" in str(error.value)


def test_demo_uses_remote_parquet_without_raw_data():
    config = load_config(Path("configs/demo.yaml"))
    assert config["data"]["source"] == "sample_parquet"
    assert Path(config["paths"]["samples"]).name == "samples_data"
    assert config["serving"]["enabled"]


def test_missing_sample_tables_report_parquet_input(tmp_path):
    config = load_config(Path("configs/demo.yaml"))
    config["paths"]["samples"] = str(tmp_path)
    with pytest.raises(FileNotFoundError, match="Missing sample Parquet tables") as error:
        validate_raw_files(config)
    assert "book_authors_map" in str(error.value)
