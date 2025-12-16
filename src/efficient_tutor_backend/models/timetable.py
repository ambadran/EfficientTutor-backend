'''
Timetable API Models
'''
from typing import Optional
from enum import Enum
from datetime import datetime, time
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class TimeTableSlotType(str, Enum):
    TUITION = "Tuition"
    AVAILABILITY = "Availability"
    OTHER = "Other"

class TimeTableSlot(BaseModel):
    """
    Unified model for a single slot in the timetable.
    Contains both absolute data from DB and relativistic calculated data.
    """
    # Absolute Data (From DB)
    id: UUID
    user_id: UUID = Field(..., description="The ID of the user this slot belongs to (e.g. the student).")
    name: str
    slot_type: TimeTableSlotType
    day_of_week: int = Field(..., description="1=Monday, 7=Sunday")
    day_name: str = Field(..., description="e.g. 'Monday'")
    start_time: time
    end_time: time
    object_uuid: Optional[UUID] = Field(None, description="ID of the Tuition or AvailabilityInterval. None if masked.")

    # Relativistic Data (Calculated based on viewer's time/timezone)
    next_occurrence_start: datetime
    next_occurrence_end: datetime

    model_config = ConfigDict(from_attributes=True)

