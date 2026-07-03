from pydantic import BaseModel

from spectacle_core.hashing import content_hash


class VersionedArtifact(BaseModel):
    node_version: str

    def compute_hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))
