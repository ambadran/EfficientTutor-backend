'''

'''
import calendar
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Literal, Annotated, Union, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, TypeAdapter

# Import the new, static enums
from ..database.db_enums import (
    LogStatusEnum, 
    TuitionLogCreateTypeEnum, 
    SubjectEnum,
    PaidStatus,
    EducationalSystemEnum
)
from .user import UserRead
from ..common.config import settings

# --- 1. API Input Models (for POST/PUT) ---

class CustomTuitionChargeInput(BaseModel):
    """
    Validates a single student charge within a custom log POST request.
    """
    student_id: UUID
    cost: Decimal

class ScheduledLogInput(BaseModel):
    """
    Validates the request body for creating a log from a SCHEDULED tuition.
    """
    # 1. The 'discriminator' field. Must be a Literal.
    log_type: Literal[TuitionLogCreateTypeEnum.SCHEDULED.value]
    
    # 2. Required fields for this type
    tuition_id: UUID
    start_time: datetime
    end_time: datetime

class CustomLogInput(BaseModel):
    """
    Validates the request body for creating a CUSTOM tuition log.
    """
    # 1. The 'discriminator' field. Must be a Literal.
    log_type: Literal[TuitionLogCreateTypeEnum.CUSTOM.value]

    # 2. Required fields for this type
    subject: SubjectEnum
    educational_system: EducationalSystemEnum
    lesson_index: int
    start_time: datetime
    end_time: datetime
    charges: list[CustomTuitionChargeInput]

# 3. The new model
TuitionLogCreateHint = Annotated[
    Union[ScheduledLogInput, CustomLogInput],
    Field(discriminator='log_type')
]

# NEW: Create the TypeAdapter for our service to import and use.
TuitionLogCreateValidator = TypeAdapter(TuitionLogCreateHint)

class PaymentLogCreate(BaseModel):
    """
    Validates the request body for creating a new payment log.
    """
    parent_id: UUID
    teacher_id: UUID
    amount_paid: Decimal
    payment_date: datetime
    notes: Optional[str] = None


# --- 2. API Output Models (for GET) ---

class LogChargeRead(BaseModel):
    """
    A lean representation of a charge within a log (for a teacher's view).
    """
    student_id: UUID
    student_name: str
    cost: Decimal

    model_config = ConfigDict(from_attributes=True)

class TuitionLogReadForTeacher(BaseModel):
    """
    The API model for a tuition log as seen by a teacher.
    """
    id: UUID
    teacher: UserRead
    subject: SubjectEnum
    educational_system: EducationalSystemEnum
    start_time: datetime
    end_time: datetime
    status: LogStatusEnum
    create_type: TuitionLogCreateTypeEnum
    tuition_id: Optional[UUID] = None
    lesson_index: Optional[int] = None
    corrected_from_log_id: Optional[UUID] = None
    paid_status: PaidStatus
    
    # We will eager-load the full charges for the teacher
    charges: list[LogChargeRead] 

    @computed_field
    @property
    def total_cost(self) -> Decimal:
        return sum(charge.cost for charge in self.charges)

    @computed_field
    @property
    def duration(self) -> str:
        duration_hours = (self.end_time - self.start_time).total_seconds() / 3600
        return f"{duration_hours:.1f}h"

    # We need a field for the week number calculation
    earliest_log_date: datetime = Field(exclude=True) # Exclude from final JSON

    @computed_field
    @property
    def week_number(self) -> int:
        def get_start_of_week(a_date: datetime) -> datetime:
            days_to_subtract = (a_date.weekday() - settings.FIRST_DAY_OF_WEEK + 7) % 7
            start_of_week_date = a_date.date() - timedelta(days=days_to_subtract)
            return datetime.combine(start_of_week_date, datetime.min.time())

        start_of_log_week = get_start_of_week(self.start_time)
        start_of_earliest_week = get_start_of_week(self.earliest_log_date)
        delta_days = (start_of_log_week - start_of_earliest_week).days
        return (delta_days // 7) + 1

    model_config = ConfigDict(from_attributes=True)

class TuitionLogReadForParent(BaseModel):
    """
    The API model for a tuition log as seen by a parent or student.
    """
    id: UUID
    subject: SubjectEnum
    educational_system: EducationalSystemEnum
    start_time: datetime
    end_time: datetime
    status: LogStatusEnum
    create_type: TuitionLogCreateTypeEnum
    tuition_id: Optional[UUID] = None
    lesson_index: Optional[int] = None
    corrected_from_log_id: Optional[UUID] = None
    paid_status: PaidStatus

    # The service will provide these fields pre-calculated
    cost: Decimal
    attendee_names: list[str]

    # We need a field for the week number calculation
    earliest_log_date: datetime = Field(exclude=True)

    @computed_field
    @property
    def duration(self) -> str:
        duration_hours = (self.end_time - self.start_time).total_seconds() / 3600
        return f"{duration_hours:.1f}h"

    @computed_field
    @property
    def week_number(self) -> int:
        def get_start_of_week(a_date: datetime) -> datetime:
            days_to_subtract = (a_date.weekday() - settings.FIRST_DAY_OF_WEEK + 7) % 7
            start_of_week_date = a_date.date() - timedelta(days=days_to_subtract)
            return datetime.combine(start_of_week_date, datetime.min.time())

        start_of_log_week = get_start_of_week(self.start_time)
        start_of_earliest_week = get_start_of_week(self.earliest_log_date)
        delta_days = (start_of_log_week - start_of_earliest_week).days
        return (delta_days // 7) + 1

    model_config = ConfigDict(from_attributes=True)

class TuitionLogReadForStudent(BaseModel):
    """
    The API model for a tuition log as seen by a STUDENT.
    Shows NO financial details.
    """
    id: UUID
    subject: SubjectEnum
    educational_system: EducationalSystemEnum
    start_time: datetime
    end_time: datetime
    status: LogStatusEnum
    create_type: TuitionLogCreateTypeEnum
    tuition_id: Optional[UUID] = None
    lesson_index: Optional[int] = None
    corrected_from_log_id: Optional[UUID] = None
    
    # As requested: no cost/charge
    attendee_names: list[str]

    # We need a field for the week number calculation
    earliest_log_date: datetime = Field(exclude=True)

    @computed_field
    @property
    def duration(self) -> str:
        duration_hours = (self.end_time - self.start_time).total_seconds() / 3600
        return f"{duration_hours:.1f}h"

    @computed_field
    @property
    def week_number(self) -> int:
        def get_start_of_week(a_date: datetime) -> datetime:
            # ... (implementation from your existing model) ...
            days_to_subtract = (a_date.weekday() - settings.FIRST_DAY_OF_WEEK + 7) % 7
            start_of_week_date = a_date.date() - timedelta(days=days_to_subtract)
            return datetime.combine(start_of_week_date, datetime.min.time())

        start_of_log_week = get_start_of_week(self.start_time)
        start_of_earliest_week = get_start_of_week(self.earliest_log_date)
        delta_days = (start_of_log_week - start_of_earliest_week).days
        return (delta_days // 7) + 1

    model_config = ConfigDict(from_attributes=True)

class PaymentLogRead(BaseModel):
    """
    The API model for a payment log.
    """
    id: UUID
    payment_date: datetime
    amount_paid: Decimal
    status: LogStatusEnum
    notes: Optional[str] = None
    corrected_from_log_id: Optional[UUID] = None
    
    # The service will pre-populate these fields
    parent_name: str
    teacher_name: str
    currency: str

    model_config = ConfigDict(from_attributes=True)


# --- 3. Financial Summary Models (Output) ---

class FinancialSummaryForParent(BaseModel):
    total_due: Decimal
    credit_balance: Decimal
    unpaid_count: int

class FinancialSummaryForTeacher(BaseModel):
    total_owed_to_teacher: Decimal
    total_credit_held: Decimal
    total_lessons_given_this_month: int



TuitionLogReadRoleBased = Union[
    TuitionLogReadForTeacher,
    TuitionLogReadForParent,
    TuitionLogReadForStudent,
]


FinancialSummaryReadRoleBased = Union[
    FinancialSummaryForParent,
    FinancialSummaryForTeacher,
]
