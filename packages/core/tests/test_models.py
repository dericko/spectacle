from spectacle_core.models import VersionedArtifact


class Dummy(VersionedArtifact):
    text: str


def test_compute_hash_stable_for_same_content():
    a = Dummy(node_version="dummy@1", text="hello")
    b = Dummy(node_version="dummy@1", text="hello")
    assert a.compute_hash() == b.compute_hash()


def test_compute_hash_changes_with_node_version_even_if_content_same():
    a = Dummy(node_version="dummy@1", text="hello")
    b = Dummy(node_version="dummy@2", text="hello")
    assert a.compute_hash() != b.compute_hash()


def test_compute_hash_changes_with_content():
    a = Dummy(node_version="dummy@1", text="hello")
    b = Dummy(node_version="dummy@1", text="goodbye")
    assert a.compute_hash() != b.compute_hash()
