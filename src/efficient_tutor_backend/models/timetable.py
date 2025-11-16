'''

'''
from typing import Union
from datetime import datetime
from pydantic import BaseModel, ConfigDict

# Import the new, role-specific tuition models
from .tuition import (
    TuitionReadForTeacher,
    TuitionReadForParent,
    TuitionReadForStudent
)

# --- API Read Models (Output) ---

class ScheduledTuitionReadForTeacher(BaseModel):
    """API model for a scheduled tuition (Teacher view)."""
    start_time: datetime
    end_time: datetime
    tuition: TuitionReadForTeacher # Nests the teacher-specific model

    model_config = ConfigDict(from_attributes=True)

class ScheduledTuitionReadForParent(BaseModel):
    """API model for a scheduled tuition (Parent view)."""
    start_time: datetime
    end_time: datetime
    tuition: TuitionReadForParent # Nests the parent-specific model

    model_config = ConfigDict(from_attributes=True)

class ScheduledTuitionReadForStudent(BaseModel):
    """API model for a scheduled tuition (Student view)."""
    start_time: datetime
    end_time: datetime
    tuition: TuitionReadForStudent # Nests the student-specific model

    model_config = ConfigDict(from_attributes=True)


ScheduledTuitionReadRoleBased = Union[
    ScheduledTuitionReadForTeacher,
    ScheduledTuitionReadForParent,
    ScheduledTuitionReadForStudent,
]
