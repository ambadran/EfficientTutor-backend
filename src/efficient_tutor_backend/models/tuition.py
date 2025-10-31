'''

'''
from datetime import timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field

from .user import UserRead  # Import the base user read model
from ..database.db_enums import SubjectEnum

# --- API Read Models (Output) ---

class TuitionChargeRead(BaseModel):
    """
    A lean Pydantic model for a tuition charge (for a teacher's view).
    """
    cost: Decimal
    student: UserRead  # Nested model for student details

    model_config = ConfigDict(from_attributes=True)

class TuitionReadForTeacher(BaseModel):
    """
    The API model for a tuition as seen by a teacher.
    """
    id: UUID
    subject: SubjectEnum
    lesson_index: int
    min_duration_minutes: int
    max_duration_minutes: int
    meeting_link: Optional[str] = None
    
    # We will eager-load the full charges and compute the total cost
    charges: list[TuitionChargeRead]

    @computed_field
    @property
    def total_cost(self) -> Decimal:
        """Calculates the total value of the tuition."""
        return sum(charge.cost for charge in self.charges)

    model_config = ConfigDict(from_attributes=True)

class TuitionReadForGuardian(BaseModel):
    """
    The API model for a tuition as seen by a parent or student.
    
    IMPORTANT: This model is designed to be populated by the *service layer*,
    which will pre-filter the charges.
    """
    id: UUID
    subject: SubjectEnum
    lesson_index: int
    min_duration_minutes: int
    max_duration_minutes: int
    meeting_link: Optional[str] = None
    
    # The service will ensure this list only contains the charge
    # relevant to the viewing parent/student.
    charges: list[TuitionChargeRead] 
    
    @computed_field
    @property
    def charge_amount(self) -> Decimal:
        """Returns the cost for the specific guardian."""
        if self.charges:
            return self.charges[0].cost
        return Decimal("0.00")

    @computed_field
    @property
    def attendee_names(self) -> list[str]:
        """
        Shows all attendees.
        NOTE: This logic will need to be handled by the service layer,
        as this model only receives its *own* charge.
        """
        # This will be populated by the service.
        return [] 

    model_config = ConfigDict(from_attributes=True)
