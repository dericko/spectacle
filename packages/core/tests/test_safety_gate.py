import pytest
from spectacle_core.nodes.safety_gate import run_safety_gate, SafetyBlockedError
from spectacle_core.models import Script, SceneNarration
from spectacle_core.domain_pack import SafetyProfile

_PROFILE = SafetyProfile(disallowed_topics=["violence"], age_rating="general")

def _script(text):
    return Script(tree_hash="t", scenes=[SceneNarration(
        scene_id="intro_1", render_hint="layout", narration_text=text,
        on_screen_text="Hi", target_duration_s=20.0, verify=False)])

def test_clean_script_passes():
    run_safety_gate(_script("Let's add fractions."), _PROFILE,
                    safety_llm_fn=lambda text, topics: [])  # no violations

def test_violation_raises():
    with pytest.raises(SafetyBlockedError):
        run_safety_gate(_script("graphic violence here"), _PROFILE,
                        safety_llm_fn=lambda text, topics: ["violence"])
