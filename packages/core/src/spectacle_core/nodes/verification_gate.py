from spectacle_core.hashing import content_hash
from spectacle_core.models import SceneGraph, VerificationResult


class VerificationBlockedError(Exception):
    pass


def run_verification_gate(scene_graph: SceneGraph, domain_pack) -> list[VerificationResult]:
    """Runs every gate domain_pack.verification_gates() returns for each
    scene. Not subject to run_mode -- always enforced, even in 'auto'."""
    results: list[VerificationResult] = []
    failures: list[str] = []

    for scene in scene_graph.scenes:
        gates = domain_pack.verification_gates(scene)
        for gate in gates:
            outcome = gate(scene)
            results.append(VerificationResult(
                scene_id=scene.scene_id,
                scene_input_hash=scene.scene_input_hash(),
                passed=outcome.passed,
                detail=outcome.detail,
            ))
            if not outcome.passed:
                failures.append(f"{scene.scene_id}: {outcome.detail}")

    if failures:
        raise VerificationBlockedError("; ".join(failures))

    return results
