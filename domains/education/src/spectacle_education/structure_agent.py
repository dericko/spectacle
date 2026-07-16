from spectacle_core.domain_pack import ContentTree, SceneStub
from spectacle_core.hashing import content_hash
from spectacle_education.lesson_plan import LessonPlan
from spectacle_education.scene_menu import budget_scenes


def structure(plan: LessonPlan) -> ContentTree:
    spec_hash = content_hash(plan.model_dump(mode="json"))
    if plan.scenes:
        stubs = [SceneStub(
            scene_id=s.scene_id, render_hint=s.render_hint, content_hint=s.content,
            target_duration_s=s.target_duration_s, verify=s.verify, expression=s.expression,
        ) for s in plan.scenes]
    else:
        objective = plan.objectives[0] if plan.objectives else ""
        stubs = budget_scenes(objective, plan.worked_example_expression_hint,
                              plan.total_duration_target_minutes or 3)
    return ContentTree(spec_hash=spec_hash, scenes=stubs)
