from pydantic import BaseModel, Field


class EducationSpec(BaseModel):
    learning_objective: str
    worked_example_expression: str
    target_duration_minutes: int = Field(ge=1, le=10)
    audience: str
