from spectacle_education.safety import education_safety_profile
from spectacle_education.spec import EducationSpec
from spectacle_education.structure_agent import structure
from spectacle_education.verification import verification_gates


class _EducationPack:
    spec_schema = EducationSpec
    structure = staticmethod(structure)
    verification_gates = staticmethod(verification_gates)
    safety_profile = education_safety_profile


education_pack = _EducationPack()
