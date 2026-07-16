class PlanConfirmationError(Exception):
    pass


def check_plan_confirmed(scenes: list[dict]) -> None:
    """Provenance/confirmation gate (distinct from the arithmetic sympy gate).
    A verify scene may only proceed if its math is confirmed AND present.
    Enforced in every run mode; in 'auto' mode intake_draft scenes stay
    unconfirmed and therefore block here."""
    bad = []
    for s in scenes:
        if not s.get("verify"):
            continue
        if not s.get("confirmed") or not s.get("expression"):
            bad.append(s.get("scene_id", "?"))
    if bad:
        raise PlanConfirmationError(
            f"verify scenes not confirmed or missing expression: {', '.join(bad)}")
