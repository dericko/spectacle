from spectacle_core.domain_pack import VerificationGate, VerificationOutcome
from spectacle_core.models import SceneGraphEntry


def sympy_equivalence_gate(scene: SceneGraphEntry) -> VerificationOutcome:
    raise NotImplementedError("implemented in Task 9")


def verification_gates(scene: SceneGraphEntry) -> list[VerificationGate]:
    if scene.verify:
        return [sympy_equivalence_gate]
    return []
