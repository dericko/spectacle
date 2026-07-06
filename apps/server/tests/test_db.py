import pytest

from server.db import ArtifactMetadataStore

PG_CONN = "postgresql://spectacle:spectacle@localhost:5432/spectacle"


@pytest.mark.integration
def test_insert_and_list_artifacts_for_a_run():
    store = ArtifactMetadataStore(PG_CONN)
    store.setup()
    store.record(run_id="run-1", content_hash="h1", stage="script", scene_id=None)
    store.record(run_id="run-1", content_hash="h2", stage="scene_final", scene_id="intro_1")
    rows = store.list_for_run("run-1")
    assert {r["content_hash"] for r in rows} == {"h1", "h2"}
