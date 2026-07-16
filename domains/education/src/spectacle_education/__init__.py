from spectacle_education.intake import intake
from spectacle_education.lesson_plan import LessonPlan
from spectacle_education.safety import education_safety_profile
from spectacle_education.structure_agent import structure
from spectacle_education.verification import verification_gates


class _EducationPack:
    spec_schema = LessonPlan
    structure = staticmethod(structure)
    intake = staticmethod(intake)
    verification_gates = staticmethod(verification_gates)
    safety_profile = education_safety_profile


education_pack = _EducationPack()
