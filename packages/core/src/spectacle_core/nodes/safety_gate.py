"""Content-safety hard gate over generated scripts.

Deliberate exception to "only deterministic checks hard-block" (the symbolic
verification gate in verification_gate.py is the other hard gate and stays
sympy-only): a single LLM call screens narration/on-screen text against
`SafetyProfile.disallowed_topics` and raises before any render. This is
justified because a false positive routes to the existing human-review
interrupt rather than silently corrupting output -- unlike verification,
where a false pass would let mathematically wrong content ship.
"""
import json as _json
from typing import Callable

import anthropic

from spectacle_core.domain_pack import SafetyProfile
from spectacle_core.models import Script
from spectacle_core.versioning import compute_fingerprint


class SafetyBlockedError(Exception):
    pass


SafetyLLMFn = Callable[[str, list[str]], list[str]]

_SAFETY_MODEL = "claude-haiku-4-5-20251001"
_SAFETY_TEMPLATE = "screen text against disallowed_topics, return matched topics as JSON list"
SAFETY_GATE_FINGERPRINT = compute_fingerprint(
    "safety_gate", _SAFETY_MODEL, _SAFETY_TEMPLATE, {"max_tokens": 200}
)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def default_safety_llm(text: str, disallowed_topics: list[str]) -> list[str]:
    prompt = (
        f"Disallowed topics: {', '.join(disallowed_topics)}\n"
        f"Text:\n{text}\n\n"
        "Reply with a JSON array of which disallowed topics (if any) this text "
        "violates. Reply with [] if none apply. Only output the JSON array."
    )
    msg = _get_client().messages.create(
        model=_SAFETY_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text_block = next(b for b in msg.content if b.type == "text")
    return _json.loads(text_block.text)


default_safety_llm.fingerprint = SAFETY_GATE_FINGERPRINT


def run_safety_gate(script: Script, profile: SafetyProfile, safety_llm_fn: SafetyLLMFn = default_safety_llm) -> None:
    """Never subject to run_mode -- always enforced, even in 'auto'."""
    text = "\n".join(f"{s.narration_text}\n{s.on_screen_text}" for s in script.scenes)
    matched = safety_llm_fn(text, profile.disallowed_topics)
    if matched:
        raise SafetyBlockedError(f"disallowed topics: {', '.join(matched)}")
