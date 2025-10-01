'''
This files handles all the finance logic
'''
import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field, Field

from ..common.logger import log
from ..database.db_handler2 import DatabaseHandler
from .users import (
    ListableEnum, UserRole, Student, Parent, Teacher, SubjectEnum,
    Students, Parents, Teachers
)
from .tuitions import Tuition, Tuitions


# --- Dynamic Enums ---
try:
    db_temp = DatabaseHandler()
    LogStatus = ListableEnum('LogStatus', {label: label for label in db_temp.get_enum_labels('log_status_enum')})
    TuitionLogCreateType = ListableEnum('TuitionLogCreateType', {label: label for label in db_temp.get_enum_labels('tuition_log_create_type_enum')})
except Exception as e:
    log.critical(f"FATAL: Could not initialize finance-related ENUMs. Error: {e}", exc_info=True)
    raise

# --- 1. Internal "Rich" Pydantic Models ---
# These models represent the complete, hydrated data for internal service layer use.

class TuitionLogCharge(BaseModel):
    """A fully hydrated representation of a single student's charge within a tuition log."""
    student: Student
    parent: Parent
    cost: Decimal
    model_config = ConfigDict(from_attributes=True)

class TuitionLog(BaseModel):
    """A fully hydrated representation of a single tuition log entry."""
    id: UUID
    teacher: Teacher
    subject: SubjectEnum
    start_time: datetime
    end_time: datetime
    status: LogStatus
    create_type: TuitionLogCreateType
    charges: list[TuitionLogCharge]
    tuition: Optional[Tuition] = None
    lesson_index: Optional[int] = None
    corrected_from_log_id: Optional[UUID] = None
    model_config = ConfigDict(from_attributes=True)

class PaymentLog(BaseModel):
    """A fully hydrated representation of a single payment log entry."""
    id: UUID
    parent: Parent
    teacher: Teacher
    payment_date: datetime
    amount_paid: Decimal
    status: LogStatus
    notes: Optional[str] = None
    corrected_from_log_id: Optional[UUID] = None
    model_config = ConfigDict(from_attributes=True)


# --- 2. API Input Pydantic Models ---
# These models validate the raw data from incoming API POST/PUT requests.

class CreateScheduledTuitionLogInput(BaseModel):
    log_type: Literal['scheduled']
    tuition_id: UUID
    start_time: datetime
    end_time: datetime

class CustomTuitionChargeInput(BaseModel):
    student_id: UUID
    cost: Decimal

class CreateCustomTuitionLogInput(BaseModel):
    log_type: Literal['custom']
    teacher_id: UUID
    subject: SubjectEnum
    lesson_index: int
    start_time: datetime
    end_time: datetime
    charges: list[CustomTuitionChargeInput]

class CreatePaymentLogInput(BaseModel):
    parent_user_id: UUID
    teacher_id: UUID
    amount_paid: Decimal
    notes: Optional[str] = None


# --- 3. API Output Pydantic Models ---
# These lean models define the exact shape of the JSON sent back to the frontend.

class ApiTuitionLog(BaseModel):
    """Defines the JSON structure for a tuition log sent to the frontend."""
    # Internal fields used for computation, excluded from final output.
    source: TuitionLog
    earliest_log_date: datetime

    @computed_field
    @property
    def id(self) -> str:
        return str(self.source.id)

    @computed_field
    @property
    def subject(self) -> str:
        return self.source.subject.value

    @computed_field
    @property
    def attendee_names(self) -> list[str]:
        names = []
        for charge in self.source.charges:
            full_name = f"{charge.student.first_name or ''} {charge.student.last_name or ''}".strip()
            names.append(full_name or "Unknown Student")
        return names

    @computed_field
    @property
    def start_time(self) -> str:
        return self.source.start_time.isoformat().replace('+00:00', 'Z')

    @computed_field
    @property
    def end_time(self) -> str:
        return self.source.end_time.isoformat().replace('+00:00', 'Z')

    @computed_field
    @property
    def duration(self) -> str:
        """Calculates duration and formats it as 'X.Yh'."""
        duration_hours = (self.source.end_time - self.source.start_time).total_seconds() / 3600
        return f"{duration_hours:.1f}h"

    @computed_field
    @property
    def cost(self) -> str:
        """Calculates the total cost of the tuition log."""
        total_cost = sum(charge.cost for charge in self.source.charges)
        return f"{total_cost:.2f}"

    @computed_field
    @property
    def status(self) -> str:
        return self.source.status.value

    @computed_field
    @property
    def create_type(self) -> str:
        return self.source.create_type.value

    @computed_field
    @property
    def week_number(self) -> int:
        """Calculates the week number relative to the first-ever log entry."""
        delta = self.source.start_time - self.earliest_log_date
        # Add 1 so the first week is week 1, not week 0
        return (delta.days // 7) + 1

    @computed_field
    @property
    def corrected_from_log_id(self) -> Optional[str]:
        return str(self.source.corrected_from_log_id) if self.source.corrected_from_log_id else None

class ApiPaymentLog(BaseModel):
    """FINALIZED: Defines the JSON structure for a payment log sent to the frontend."""
    source: PaymentLog

    @computed_field
    @property
    def id(self) -> str:
        return str(self.source.id)

    @computed_field
    @property
    def parent_name(self) -> str:
        p = self.source.parent
        full_name = f"{p.first_name or ''} {p.last_name or ''}".strip()
        return full_name or "Unknown Parent"

    @computed_field
    @property
    def teacher_name(self) -> str:
        t = self.source.teacher
        full_name = f"{t.first_name or ''} {t.last_name or ''}".strip()
        return full_name or "Unknown Teacher"

    @computed_field
    @property
    def payment_date(self) -> str:
        return self.source.payment_date.isoformat().replace('+00:00', 'Z')

    @computed_field
    @property
    def amount_paid(self) -> Decimal:
        return self.source.amount_paid

    @computed_field
    @property
    def currency(self) -> str:
        return self.source.parent.currency

    @computed_field
    @property
    def status(self) -> str:
        return self.source.status.value

    @computed_field
    @property
    def notes(self) -> Optional[str]:
        return self.source.notes

    @computed_field
    @property
    def corrected_from_log_id(self) -> Optional[str]:
        return str(self.source.corrected_from_log_id) if self.source.corrected_from_log_id else None


# --- 4. Main Service Class ---

class Finance:
    """
    Service class for managing all financial operations, including tuition and payment logs.
    """
    def __init__(self):
        self.db = DatabaseHandler()
        # Instantiate other services this class depends on
        self.students_service = Students()
        self.parents_service = Parents()
        self.tuitions_service = Tuitions()

    # --- Tuition Log - Write Operations ---

    def create_tuition_log(self, log_data: dict[str, Any], corrected_from_log_id: Optional[UUID] = None) -> Optional[TuitionLog]:
        """
        Public dispatcher method to create a new tuition log.
        It validates the input and calls the appropriate private helper based on 'log_type'.
        """
        log_type = log_data.get('log_type')
        try:
            if log_type == 'scheduled':
                input_model = CreateScheduledTuitionLogInput.model_validate(log_data)
                return self._create_from_scheduled(input_model, corrected_from_log_id)
            elif log_type == 'custom':
                input_model = CreateCustomTuitionLogInput.model_validate(log_data)
                return self._create_from_custom(input_model, corrected_from_log_id)
            else:
                log.error(f"Invalid log_type provided: {log_type}")
                return None
        except ValidationError as e:
            log.error(f"Pydantic validation failed for creating tuition log. Data: {log_data}, Error: {e}")
            # In a real API, you'd raise an exception here to return a 422 error
            return None

    def _create_from_scheduled(self, data: CreateScheduledTuitionLogInput, corrected_from_log_id: Optional[UUID]) -> Optional[TuitionLog]:
        """Private helper to create a log from a scheduled tuition."""
        log.info(f"Creating SCHEDULED log from tuition ID {data.tuition_id}.")
        # Fetch the full Tuition object to get its details
        tuition = self.tuitions_service.get_by_id(data.tuition_id)
        if not tuition:
            log.error(f"Cannot create scheduled log: Tuition with ID {data.tuition_id} not found.")
            return None

        # Prepare the charges data by copying it from the scheduled tuition
        charges_to_create = [
            {
                'student_id': charge.student.id,
                'parent_id': charge.parent.id,
                'cost': charge.cost
            } for charge in tuition.charges
        ]
        
        new_log_id = self.db.create_tuition_log_and_charges(
            teacher_id=tuition.teacher.id,
            subject=tuition.subject.value,
            start_time=data.start_time,
            end_time=data.end_time,
            create_type=TuitionLogCreateType.SCHEDULED.value,
            charges=charges_to_create,
            tuition_id=tuition.id,
            lesson_index=tuition.lesson_index,
            corrected_from_log_id=corrected_from_log_id
        )
        return self.get_tuition_log_by_id(new_log_id) if new_log_id else None

    def _create_from_custom(self, data: CreateCustomTuitionLogInput, corrected_from_log_id: Optional[UUID]) -> Optional[TuitionLog]:
        """Private helper to create a log from custom data."""
        log.info(f"Creating CUSTOM log for teacher {data.teacher_id}.")
        # Eager load all students for efficient parent_id lookup
        all_students_dict = {s.id: s for s in self.students_service.get_all()}
        
        charges_to_create = []
        for charge_input in data.charges:
            student = all_students_dict.get(charge_input.student_id)
            if not student:
                log.error(f"Cannot create custom log: Student with ID {charge_input.student_id} not found.")
                return None
            
            charges_to_create.append({
                'student_id': student.id,
                'parent_id': student.parent_id, # The required lookup
                'cost': charge_input.cost
            })

        new_log_id = self.db.create_tuition_log_and_charges(
            teacher_id=data.teacher_id,
            subject=data.subject.value,
            start_time=data.start_time,
            end_time=data.end_time,
            create_type=TuitionLogCreateType.CUSTOM.value,
            charges=charges_to_create,
            lesson_index=data.lesson_index,
            corrected_from_log_id=corrected_from_log_id
        )
        return self.get_tuition_log_by_id(new_log_id) if new_log_id else None

    def edit_tuition_log(self, old_log_id: UUID, new_log_data: dict[str, Any]) -> Optional[TuitionLog]:
        """Edits a tuition log by voiding the old one and creating a new, corrected one."""
        log.info(f"Editing tuition log {old_log_id} by voiding and creating a new log.")
        # Step 1: Void the old log
        if not self.db.set_log_status('tuition_logs', old_log_id, LogStatus.VOID.value):
            log.error(f"Failed to void old tuition log {old_log_id}. Aborting edit.")
            return None
        
        # Step 2: Create the new log, linking it back to the old one
        return self.create_tuition_log(new_log_data, corrected_from_log_id=old_log_id)

    def delete_tuition_log(self, log_id: UUID) -> bool:
        """'Deletes' a tuition log by setting its status to VOID."""
        return self.db.set_log_status('tuition_logs', log_id, LogStatus.VOID.value)

    # --- Payment Log - Write Operations ---

    def create_payment_log(self, log_data: dict[str, Any], corrected_from_log_id: Optional[UUID] = None) -> Optional[PaymentLog]:
        """Creates a new payment log after validating input data."""
        try:
            input_model = CreatePaymentLogInput.model_validate(log_data)
            new_log_id = self.db.create_payment_log(
                parent_user_id=input_model.parent_user_id,
                teacher_id=input_model.teacher_id,
                amount_paid=input_model.amount_paid,
                notes=input_model.notes,
                corrected_from_log_id=corrected_from_log_id
            )
            return self.get_payment_log_by_id(new_log_id) if new_log_id else None
        except ValidationError as e:
            log.error(f"Pydantic validation failed for creating payment log. Data: {log_data}, Error: {e}")
            return None

    def edit_payment_log(self, old_log_id: UUID, new_log_data: dict[str, Any]) -> Optional[PaymentLog]:
        """Edits a payment log by voiding the old one and creating a new one."""
        log.info(f"Editing payment log {old_log_id} by voiding and creating a new log.")
        if not self.db.set_log_status('payment_logs', old_log_id, LogStatus.VOID.value):
            log.error(f"Failed to void old payment log {old_log_id}. Aborting edit.")
            return None
        
        return self.create_payment_log(new_log_data, corrected_from_log_id=old_log_id)

    def delete_payment_log(self, log_id: UUID) -> bool:
        """'Deletes' a payment log by setting its status to VOID."""
        return self.db.set_log_status('payment_logs', log_id, LogStatus.VOID.value)
        
    # --- Read Operations (Internal) ---

    def get_tuition_log_by_id(self, log_id: UUID) -> Optional[TuitionLog]:
        """Fetches a single, fully hydrated tuition log by its ID."""
        # This would require a new DB method `get_tuition_log_by_id`
        # For now, we can filter from a larger list as a simple implementation.
        # In a real-world scenario, a dedicated DB call is better.
        # This is a placeholder for that logic.
        pass

    def get_payment_log_by_id(self, log_id: UUID) -> Optional[PaymentLog]:
        pass # Placeholder

    def get_tuition_logs_by_teacher(self, teacher_id: UUID) -> list[TuitionLog]:
        """Fetches all tuition logs for a teacher, returning rich Pydantic models."""
        raw_logs = self.db.get_tuition_logs_by_teacher(teacher_id)
        return [TuitionLog.model_validate(data) for data in raw_logs]

    def get_tuition_logs_by_parent(self, parent_id: UUID) -> list[TuitionLog]:
        """Fetches all tuition logs for a parent, returning rich Pydantic models."""
        raw_logs = self.db.get_tuition_logs_by_parent(parent_id)
        return [TuitionLog.model_validate(data) for data in raw_logs]

    def get_payment_logs_by_teacher(self, teacher_id: UUID) -> list[PaymentLog]:
        """Fetches all payment logs for a teacher, returning rich Pydantic models."""
        raw_logs = self.db.get_payment_logs_by_teacher(teacher_id)
        return [PaymentLog.model_validate(data) for data in raw_logs]

    def get_payment_logs_by_parent(self, parent_id: UUID) -> list[PaymentLog]:
        """Fetches all payment logs for a parent, returning rich Pydantic models."""
        raw_logs = self.db.get_payment_logs_by_parent(parent_id)
        return [PaymentLog.model_validate(data) for data in raw_logs]
    
    # --- Read Operations (for API) ---

    def get_tuition_logs_for_api(self, view_id: UUID) -> list[dict[str, Any]]:
        """
        Fetches tuition logs for the API, formatted for the frontend.
        """
        log.info(f"Fetching tuition logs for API requested by user {view_id}")
        # This will now raise UserNotFoundError if the user doesn't exist.
        role = self.db.identify_user_role(view_id)
        
        rich_logs = []
        if role == UserRole.teacher.name:
            rich_logs = self.get_tuition_logs_by_teacher(view_id)
        elif role == UserRole.parent.name:
            rich_logs = self.get_tuition_logs_by_parent(view_id)
        else:
            # CHANGED: Raise a specific authorization error.
            raise UnauthorizedRoleError(f"User with role '{role}' is not authorized to view tuition logs.")
        
        if not rich_logs:
            return []
            
        earliest_date = self.db.get_earliest_log_start_time()
        if not earliest_date:
            earliest_date = datetime.now()

        api_models = [ApiTuitionLog(source=log, earliest_log_date=earliest_date) for log in rich_logs]
        return [model.model_dump(exclude={'source', 'earliest_log_date'}) for model in api_models]

    def get_payment_logs_for_api(self, view_id: UUID) -> list[dict[str, Any]]:
        """Fetches payment logs for the API, formatted for the frontend."""
        log.info(f"Fetching payment logs for API requested by user {view_id}")
        role = self.db.identify_user_role(view_id)

        rich_logs = []
        if role == UserRole.teacher.name:
            rich_logs = self.get_payment_logs_by_teacher(view_id)
        elif role == UserRole.parent.name:
            rich_logs = self.get_payment_logs_by_parent(view_id)
        else:
            # CHANGED: Raise a specific authorization error.
            raise UnauthorizedRoleError(f"User with role '{role}' is not authorized to view payment logs.")
            
        api_models = [ApiPaymentLog(source=log) for log in rich_logs]
        return [model.model_dump(exclude={'source'}) for model in api_models]
