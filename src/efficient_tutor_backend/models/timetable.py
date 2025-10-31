# In models/timetable.py

from datetime import datetime
from pydantic import BaseModel, ConfigDict

# Import the new, role-specific tuition models
from .tuition import TuitionReadForTeacher, TuitionReadForGuardian

# --- API Read Models (Output) ---

class ScheduledTuitionReadForTeacher(BaseModel):
    """
    The API model for a scheduled tuition as seen by a teacher.
    It nests the detailed TuitionReadForTeacher model.
    """
    start_time: datetime
    end_time: datetime
    tuition: TuitionReadForTeacher

    model_config = ConfigDict(from_attributes=True)

class ScheduledTuitionReadForGuardian(BaseModel):
    """
    The API model for a scheduled tuition as seen by a parent or student.
    It nests the filtered TuitionReadForGuardian model.
    """
    start_time: datetime
    end_time: datetime
    tuition: TuitionReadForGuardian

    model_config = ConfigDict(from_attributes=True)
