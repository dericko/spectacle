import pytest
from spectacle_core.nodes.plan_gate import check_plan_confirmed, PlanConfirmationError


def _s(scene_id, verify, confirmed, expression):
    return {"scene_id": scene_id, "verify": verify, "confirmed": confirmed, "expression": expression}


def test_confirmed_verify_scene_passes():
    check_plan_confirmed([_s("we_1", True, True, "3/4 + 1/8")])  # no raise


def test_unverified_scene_needs_nothing():
    check_plan_confirmed([_s("intro_1", False, False, None)])  # no raise


def test_unconfirmed_verify_scene_blocks():
    with pytest.raises(PlanConfirmationError) as e:
        check_plan_confirmed([_s("we_1", True, False, "3/4 + 1/8")])
    assert "we_1" in str(e.value)


def test_verify_scene_missing_expression_blocks():
    with pytest.raises(PlanConfirmationError):
        check_plan_confirmed([_s("we_1", True, True, None)])
