import shutil
from pathlib import Path

import pytest

from scripts.setup_demo import prepare_bundle, sha256


@pytest.fixture
def checkout(tmp_path):
    root = Path(__file__).resolve().parent.parent
    shutil.copytree(root / "demo_assets", tmp_path / "demo_assets")
    return tmp_path


def test_new_checkout_can_bootstrap_and_load_the_real_demo_model(checkout):
    from books_recommender.serving.runtime import DemoRecommender

    run = prepare_bundle(checkout)
    assert run == checkout / "artifacts" / "remote-demo"
    assert not (run / "config.yaml").exists()  # no original machine paths required
    engine = DemoRecommender(run / "serving")
    assert len(engine.items) == 9914
    source_ids = list(engine.aliases)[:5]
    id_map = {str(100 + i): value for i, value in enumerate(source_ids)}
    result = engine.rerank({"candidates": list(id_map)}, id_map)
    assert result["run_id"] == "remote-demo"
    assert result["books"]
    assert {row["id"] for row in result["books"]} <= set(id_map)
    assert (checkout / "artifacts" / "LATEST").read_text() == "remote-demo"


def test_setup_does_not_replace_an_existing_run(checkout):
    run = prepare_bundle(checkout)
    before = sha256(run / "serving" / "manifest.json")
    marker = run / "keep-local-file.txt"
    marker.write_text("local work")
    assert prepare_bundle(checkout) == run
    assert sha256(run / "serving" / "manifest.json") == before
    assert marker.read_text() == "local work"


def test_setup_rejects_a_corrupt_archive_before_creating_a_run(checkout):
    archive = checkout / "demo_assets" / "remote-demo-serving.tar.gz"
    with archive.open("ab") as handle:
        handle.write(b"corrupt")
    with pytest.raises(ValueError, match="checksum mismatch"):
        prepare_bundle(checkout)
    assert not (checkout / "artifacts" / "remote-demo").exists()
