from spectacle_education import education_pack
from spectacle_education.lesson_plan import LessonPlan


def test_education_pack_spec_schema_is_lesson_plan():
    assert education_pack.spec_schema is LessonPlan


def test_education_pack_intake_returns_intake_result_shaped_object():
    def fake_llm(raw, chat):
        return {"plan": None, "questions": ["What grade level?"]}

    result = education_pack.intake("x", [], llm_fn=fake_llm)

    assert result.plan is None
    assert result.clarifying_questions == ["What grade level?"]
