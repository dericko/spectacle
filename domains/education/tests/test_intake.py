from spectacle_education.intake import intake, IntakeResult, lift_legacy_spec


def test_below_threshold_returns_questions_not_plan():  # A5
    def fake_llm(raw, chat):
        return {"plan": None, "questions": ["What grade level?"]}
    result = intake("teach fractions", [], llm_fn=fake_llm)
    assert result.plan is None
    assert result.clarifying_questions == ["What grade level?"]


def test_ready_input_compiles_a_plan():
    def fake_llm(raw, chat):
        return {"plan": {"objectives": ["add unlike fractions"], "audience": "grade 4",
                         "scenes": [{"scene_id": "worked_example_1", "type": "worked_example",
                                     "render_hint": "equation_morph", "content": "solve",
                                     "verify": True, "expression": "3/4 + 1/8",
                                     "source": "author"}]},
                "questions": []}
    result = intake("...", [], llm_fn=fake_llm)
    assert result.plan is not None
    assert result.plan.scenes[0].confirmed is True  # author-supplied


def test_readiness_enforced_in_code_even_if_llm_returns_a_thin_plan():  # A5 safety net
    # LLM returns a "plan" with no objectives -> intake must downgrade to questions.
    def fake_llm(raw, chat):
        return {"plan": {"objectives": [], "audience": "", "scenes": []}, "questions": []}
    result = intake("...", [], llm_fn=fake_llm)
    assert result.plan is None and result.clarifying_questions


def test_legacy_spec_lifts_to_minimal_plan():
    plan = lift_legacy_spec({"learning_objective": "add fractions",
                             "worked_example_expression": "3/4 + 1/8",
                             "target_duration_minutes": 3, "audience": "grade 4"})
    assert plan.objectives == ["add fractions"]
    assert plan.worked_example_expression_hint == "3/4 + 1/8"
    assert plan.scenes == []  # thin → structure() will use the menu fallback
