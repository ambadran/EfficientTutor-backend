'''
This files handles all the finance logic
'''
import enum
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field, Field, ValidationError

from ..common.logger import log
from ..common.config import FIRST_DAY_OF_WEEK
from ..common.exceptions import UserNotFoundError, UnauthorizedRoleError
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


# internal Enums
class PaidStatus(str, enum.Enum):
    PAID = "Paid"
    UNPAID = "Unpaid"

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
    tuition_id: Optional[UUID] = None
    lesson_index: Optional[int] = None
    corrected_from_log_id: Optional[UUID] = None

    # A field to hold the calculated status. It's not from the DB.
    paid_status: Optional[PaidStatus] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def total_cost(self) -> Decimal:
        """A helper property to get the total cost of this specific log."""
        return sum(charge.cost for charge in self.charges)


    def __repr__(self) -> str:
        """Provides a developer-friendly representation for debugging."""
        return (
            f"TuitionLog(id={self.id!r}, subject='{self.subject.value}', "
            f"start_time='{self.start_time.isoformat()}', status='{self.status.value}', "
            f"students={len(self.charges)}, "
            f"create_type={self.create_type.value})"
        )

    def __str__(self) -> str:
        """Provides a human-readable summary of the tuition log."""
        attendee_names = ", ".join(
            [c.student.first_name for c in self.charges if c.student.first_name]
        ) or f"{len(self.charges)} student(s)"
        
        time_format = "%b %d at %H:%M" # e.g., "Oct 06 at 14:30"
        start_formatted = self.start_time.strftime(time_format)
        
        # Add a status indicator only if the log is not ACTIVE
        status_indicator = f" [{self.status.value}]"         
        return f"{self.subject.value} log for {attendee_names} on {start_formatted}{status_indicator}"

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
    parent_id: UUID
    teacher_id: UUID
    amount_paid: Decimal
    payment_date: datetime
    notes: Optional[str] = None


# --- 3. API Output Pydantic Models ---
# These lean models define the exact shape of the JSON sent back to the frontend.

class ApiLogCharge(BaseModel):
    """A lean representation of a charge within a log for the teacher's view."""
    student_id: str
    student_name: str
    cost: str

class ApiTuitionLogForGuardian(BaseModel):
    """Defines the JSON structure for a tuition log sent to the frontend."""
    # Internal fields used for computation, excluded from final output.
    source: TuitionLog
    earliest_log_date: datetime
    viewer_id: UUID

    # --- Helper method for week calculation ---
    def _get_start_of_week(self, a_date: datetime) -> datetime:
        """Finds the date of the first day of the week for a given date."""
        # Calculate how many days to subtract to get to the first day of the week
        days_to_subtract = (a_date.weekday() - FIRST_DAY_OF_WEEK + 7) % 7
        # Return the date of that day, keeping the time as the start of the day
        start_of_week_date = a_date.date() - timedelta(days=days_to_subtract)
        return datetime.combine(start_of_week_date, datetime.min.time())

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
        """Finds the specific cost for the viewer (parent or their child)."""
        cost = 0
        for charge in self.source.charges:
            if charge.parent.id == self.viewer_id or charge.student.id == self.viewer_id:
                cost += charge.cost
        return f"{cost:.2f}"

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
    def tuition_id(self) -> Optional[str]:
        """
        Returns the original tuition template ID if the log was created
        from a scheduled tuition, otherwise null.
        """
        tuition_id = self.source.tuition_id
        if tuition_id is None:
            return tuition_id
        return str(tuition_id)

    @computed_field
    @property
    def week_number(self) -> int:
        """
        REVISED: Calculates the week number relative to the first-ever log entry,
        with the week starting on the configured FIRST_DAY_OF_WEEK.
        """
        # Find the true start of the week for both dates
        start_of_log_week = self._get_start_of_week(self.source.start_time)
        start_of_earliest_week = self._get_start_of_week(self.earliest_log_date)

        # Calculate the number of full weeks between these two dates
        delta_days = (start_of_log_week - start_of_earliest_week).days
        
        # Add 1 so the first week is week 1, not week 0
        return (delta_days // 7) + 1

    @computed_field
    @property
    def corrected_from_log_id(self) -> Optional[str]:
        return str(self.source.corrected_from_log_id) if self.source.corrected_from_log_id else None

    @computed_field
    @property
    def paid_status(self) -> str:
        """Returns the pre-calculated paid status from the source object."""
        # The service layer has already done the hard work of calculating this.
        if self.source.paid_status:
            return self.source.paid_status.value
        # Fallback in case status was not calculated
        return PaidStatus.UNPAID.value

class ApiTuitionLogForTeacher(BaseModel):
    """Defines the JSON structure for a tuition log sent to the frontend."""
    # Internal fields used for computation, excluded from final output.
    source: TuitionLog
    earliest_log_date: datetime

    # --- Helper method for week calculation ---
    def _get_start_of_week(self, a_date: datetime) -> datetime:
        """Finds the date of the first day of the week for a given date."""
        # Calculate how many days to subtract to get to the first day of the week
        days_to_subtract = (a_date.weekday() - FIRST_DAY_OF_WEEK + 7) % 7
        # Return the date of that day, keeping the time as the start of the day
        start_of_week_date = a_date.date() - timedelta(days=days_to_subtract)
        return datetime.combine(start_of_week_date, datetime.min.time())

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
    def status(self) -> str:
        return self.source.status.value

    @computed_field
    @property
    def create_type(self) -> str:
        return self.source.create_type.value

    @computed_field
    @property
    def tuition_id(self) -> Optional[str]:
        """
        Returns the original tuition template ID if the log was created
        from a scheduled tuition, otherwise null.
        """
        tuition_id = self.source.tuition_id
        if tuition_id is None:
            return tuition_id
        return str(tuition_id)

    @computed_field
    @property
    def week_number(self) -> int:
        """
        REVISED: Calculates the week number relative to the first-ever log entry,
        with the week starting on the configured FIRST_DAY_OF_WEEK.
        """
        # Find the true start of the week for both dates
        start_of_log_week = self._get_start_of_week(self.source.start_time)
        start_of_earliest_week = self._get_start_of_week(self.earliest_log_date)

        # Calculate the number of full weeks between these two dates
        delta_days = (start_of_log_week - start_of_earliest_week).days
        
        # Add 1 so the first week is week 1, not week 0
        return (delta_days // 7) + 1

    @computed_field
    @property
    def corrected_from_log_id(self) -> Optional[str]:
        return str(self.source.corrected_from_log_id) if self.source.corrected_from_log_id else None

    @computed_field
    @property
    def paid_status(self) -> str:
        """Returns the pre-calculated paid status from the source object."""
        # The service layer has already done the hard work of calculating this.
        if self.source.paid_status:
            return self.source.paid_status.value
        # Fallback in case status was not calculated
        return PaidStatus.UNPAID.value

    @computed_field
    @property
    def total_cost(self) -> str:
        """Calculates the total value of the tuition log."""
        return f"{self.source.total_cost:.2f}"
    

    @computed_field
    @property
    def charges(self) -> list[ApiLogCharge]:
        """
        REVISED: Provides a detailed list of student charges for the teacher,
        now including the student_id.
        """
        charge_list = []
        for c in self.source.charges:
            student_name = f"{c.student.first_name or ''} {c.student.last_name or ''}".strip() or "Unknown"
            charge_list.append(
                ApiLogCharge(
                    student_id=str(c.student.id), # Pass the student's ID
                    student_name=student_name,
                    cost=f"{c.cost:.2f}"
                )
            )
        return charge_list

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

    def create_tuition_log(self, log_data: dict[str, Any], corrected_from_log_id: Optional[UUID] = None) -> TuitionLog:
        """
        Public dispatcher to create a new tuition log.
        Raises ValidationError on invalid input.
        """
        log_type = log_data.get('log_type')
        if log_type is None:
            raise ValueError("log_type is None, incomplete/corrupted log")
        log_type = log_type.upper()
        new_log_object: Optional[TuitionLog] = None
        try:
            # Step 1: Validate input and create the rich TuitionLog object
            if log_type == TuitionLogCreateType.SCHEDULED.value:
                input_model = CreateScheduledTuitionLogInput.model_validate(log_data)
                new_log_object = self._create_from_scheduled(input_model, corrected_from_log_id)

            elif log_type == TuitionLogCreateType.CUSTOM.value:
                input_model = CreateCustomTuitionLogInput.model_validate(log_data)
                new_log_object = self._create_from_custom(input_model, corrected_from_log_id)

            else:
                raise ValueError(f"Invalid log_type provided: {log_type}")

        except (ValidationError, ValueError) as e:
            log.error(f"Validation failed for creating tuition log. Data: {log_data}, Error: {e}")
            raise

        if not new_log_object:
            # This should not happen if creation is successful, but it's a safe check
            raise Exception("Tuition log creation did not return a valid object.")

        # Step 2: Transform the rich object into the lean API model
        earliest_date = self.db.get_earliest_log_start_time() or datetime.now()
        api_model = ApiTuitionLogForTeacher(source=new_log_object, earliest_log_date=earliest_date)
        
        # Step 3: Convert the API model to a dictionary and return
        return api_model.model_dump(exclude={'source', 'earliest_log_date'})

    def _create_from_scheduled(self, data: CreateScheduledTuitionLogInput, corrected_from_log_id: Optional[UUID]) -> TuitionLog:
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

        if not new_log_id:
            raise Exception("Failed to create tuition log in the database. Got error:\n{e}")

        return self.get_tuition_log_by_id(new_log_id)

    def _create_from_custom(self, data: CreateCustomTuitionLogInput, corrected_from_log_id: Optional[UUID]) -> TuitionLog:
        """Private helper to create a log from custom data."""
        log.info(f"Creating CUSTOM log for teacher {data.teacher_id}.")

        # OPTIMIZED: Fetch only the required students instead of all of them.
        student_ids = [charge.student_id for charge in data.charges]
        students_data = self.db.get_users_by_ids(student_ids)
        students_dict = {s['id']: Student.model_validate(s) for s in students_data}
        
        charges_to_create = []
        for charge_input in data.charges:
            student = students_dict.get(charge_input.student_id)
            if not student:
                raise ValueError(f"Cannot create custom log: Student with ID {charge_input.student_id} not found.")
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
        if not new_log_id:
            raise Exception("Failed to create tuition log in the database.")
        return self.get_tuition_log_by_id(new_log_id)

    def edit_tuition_log(self, old_log_id: UUID, new_log_data: dict[str, Any]) -> Optional[TuitionLog]:
        """Edits a tuition log by voiding the old one and creating a new, corrected one."""
        log.info(f"Editing tuition log {old_log_id} by voiding and creating a new log.")
        # Step 1: Void the old log
        if not self.db.set_log_status('tuition_logs', old_log_id, LogStatus.VOID.value):
            raise Exception(f"Failed to void old tuition log {old_log_id}. Aborting edit.")

        # Step 2: Create the new log, linking it back to the old one
        return self.create_tuition_log(new_log_data, corrected_from_log_id=old_log_id)

    def delete_tuition_log(self, log_id: UUID) -> bool:
        """'Deletes' a tuition log by setting its status to VOID."""
        return self.db.set_log_status('tuition_logs', log_id, LogStatus.VOID.value)

    # --- Payment Log - Write Operations ---

    def create_payment_log(self, log_data: dict[str, Any], corrected_from_log_id: Optional[UUID] = None) -> Optional[PaymentLog]:
        """Creates a new payment log after validating input data."""
        try:
            log.info(f"Creating new payment log..")
            input_model = CreatePaymentLogInput.model_validate(log_data)

            new_log_id = self.db.create_payment_log(
                parent_id=input_model.parent_id,
                teacher_id=input_model.teacher_id,
                amount_paid=input_model.amount_paid,
                payment_date=input_model.payment_date,
                notes=input_model.notes,
                corrected_from_log_id=corrected_from_log_id
            )

            new_log_object = self.get_payment_log_by_id(new_log_id)
            if not new_log_object:
                 raise Exception(f"Could not fetch newly created payment log with ID {new_log_id}.")

            api_model = ApiPaymentLog(source=new_log_object)
            return api_model.model_dump(exclude={'source'})

        except (ValidationError, ValueError) as e:
            log.error(f"Pydantic validation failed for creating payment log. Data: {log_data}, Error: {e}")
            raise

    def edit_payment_log(self, old_log_id: UUID, new_log_data: dict[str, Any]) -> Optional[PaymentLog]:
        """Edits a payment log by voiding the old one and creating a new one."""
        log.info(f"Editing payment log {old_log_id}...")
        if not self.db.set_log_status('payment_logs', old_log_id, LogStatus.VOID.value):
            raise Exception(f"Failed to void old payment log {old_log_id}. Aborting edit.")
        return self.create_payment_log(new_log_data, corrected_from_log_id=old_log_id)

    def delete_payment_log(self, log_id: UUID) -> bool:
        """'Deletes' a payment log by setting its status to VOID."""
        return self.db.set_log_status('payment_logs', log_id, LogStatus.VOID.value)
        
    # --- Read Operations (Internal) ---
    def get_tuition_log_by_id(self, log_id: UUID) -> Optional[TuitionLog]:
        """IMPLEMENTED: Fetches a single, fully hydrated tuition log by its ID."""
        raw_log = self.db.get_tuition_log_by_id(log_id)
        if not raw_log:
            return None
        return TuitionLog.model_validate(raw_log)

    def get_tuition_logs_by_teacher(self, teacher_id: UUID) -> list[TuitionLog]:
        """Fetches all tuition logs for a teacher, returning rich Pydantic models."""
        raw_logs = self.db.get_tuition_logs_by_teacher(teacher_id)
        if not raw_logs:
            return []

        #### getting paid/unpaid status
        # FIXED: Use consistent UUID objects as dictionary keys.
        logs_by_parent = {}
        for data in raw_logs:
            # The 'id' from the raw JSON-like data is a string, convert it to UUID.
            parent_id = UUID(data['charges'][0]['parent']['id'])
            if parent_id not in logs_by_parent:
                logs_by_parent[parent_id] = []
            logs_by_parent[parent_id].append(data)

        all_parent_ids = list(logs_by_parent.keys())
        parent_payments = self.db.get_total_payments_for_parents(all_parent_ids)

        hydrated_logs = []
        # Apply FIFO logic for each parent's group of logs
        for parent_id, logs_data in logs_by_parent.items():
            remaining_credit = parent_payments.get(parent_id, Decimal(0))
            for data in logs_data: # These are already sorted ASC by date
                log = TuitionLog.model_validate(data)
                if remaining_credit >= log.total_cost:
                    log.paid_status = PaidStatus.PAID
                    remaining_credit -= log.total_cost
                else:
                    log.paid_status = PaidStatus.UNPAID
                hydrated_logs.append(log)
        
        # Return the final list, sorted DESC for the API
        return sorted(hydrated_logs, key=lambda log: log.start_time, reverse=True)

    def get_tuition_logs_by_parent(self, parent_id: UUID) -> list[TuitionLog]:
        """Fetches all tuition logs for a parent, returning rich Pydantic models."""
        # 1. Get financial aggregates for this parent
        aggregates = self.db.get_parent_financial_aggregates(parent_id)
        remaining_credit = aggregates.get('total_payments', Decimal(0))

        # 2. Get all logs for this parent, sorted chronologically (ASC)
        raw_logs = self.db.get_tuition_logs_by_parent(parent_id)

        # 3. Apply FIFO logic
        hydrated_logs = []
        for data in raw_logs:
            log = TuitionLog.model_validate(data)
            if remaining_credit >= log.total_cost:
                log.paid_status = PaidStatus.PAID
                remaining_credit -= log.total_cost
            else:
                log.paid_status = PaidStatus.UNPAID
            hydrated_logs.append(log)

        # 4. Return the final list, sorted DESC for the API
        return sorted(hydrated_logs, key=lambda log: log.start_time, reverse=True)

    def get_payment_log_by_id(self, log_id: UUID) -> Optional[PaymentLog]:
        """NEW: Fetches a single, fully hydrated payment log by its ID."""
        raw_log = self.db.get_payment_log_by_id(log_id)
        if not raw_log:
            return None
        return PaymentLog.model_validate(raw_log)

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
            # Raise a specific authorization error.
            raise UnauthorizedRoleError(f"User with role '{role}' is not authorized to view tuition logs.")
        
        if not rich_logs:
            return []

        earliest_date = self.db.get_earliest_log_start_time() or datetime.now()

        # Dispatch to the correct formatter based on role
        if role == UserRole.teacher.name:
            return self._format_logs_for_teacher_api(rich_logs, earliest_date)
        else: # Parent or Student
            return self._format_logs_for_guardian_api(rich_logs, earliest_date, view_id)

    def _format_logs_for_teacher_api(self, logs: list[TuitionLog], earliest_date: datetime) -> list[dict]:
        """Formats a list of tuition logs for a teacher's view."""
        api_models = [ApiTuitionLogForTeacher(source=log, earliest_log_date=earliest_date) for log in logs]
        return [model.model_dump(exclude={'source', 'earliest_log_date'}) for model in api_models]

    def _format_logs_for_guardian_api(self, logs: list[TuitionLog], earliest_date: datetime, viewer_id: UUID) -> list[dict]:
        """Formats a list of tuition logs for a parent's or student's view."""
        api_models = [ApiTuitionLogForGuardian(source=log, earliest_log_date=earliest_date, viewer_id=viewer_id) for log in logs]
        return [model.model_dump(exclude={'source', 'earliest_log_date', 'viewer_id'}) for model in api_models]

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

    # -- Financial Summaries --

    def get_financial_summary(self, viewer_id: UUID) -> dict[str, Any]:
        """
        Public dispatcher method to get a financial summary for a given user.
        It identifies the user's role and calls the appropriate helper.

        Raises:
            UserNotFoundError: If the viewer_id does not correspond to a user.
            UnauthorizedRoleError: If the user's role is not 'parent' or 'teacher'.
        """
        log.info(f"Generating financial summary for user {viewer_id}.")
        role = self.db.identify_user_role(viewer_id)

        if role == UserRole.parent.name:
            return self._get_summary_for_parent(viewer_id)
        elif role == UserRole.teacher.name:
            return self._get_summary_for_teacher(viewer_id)
        else:
            raise UnauthorizedRoleError(f"User with role '{role}' is not authorized to view a financial summary.")

    def _get_summary_for_parent(self, parent_id: UUID) -> dict[str, str]:
        """Calculates and returns the financial summary for a parent."""
        
        # 1. Fetch the raw aggregates from the database
        aggregates = self.db.get_parent_financial_aggregates(parent_id)
        total_charges = aggregates.get('total_charges', Decimal(0))
        total_payments = aggregates.get('total_payments', Decimal(0))

        # 2. Calculate the running balance
        balance = total_payments - total_charges

        # 3. Determine the final summary values
        total_due = max(Decimal(0), -balance)
        credit_balance = max(Decimal(0), balance)

        # 4. Calculate unpaid_count
        #TODO: re-implement this properly
        unpaid_count = 0
        if total_due > 0:
            # If the parent owes money, count how many lessons they have.
            unpaid_count = self.db.count_parent_active_logs(parent_id)

        # 5. Return the formatted dictionary
        return {
            "total_due": f"{total_due:.2f}",
            "credit_balance": f"{credit_balance:.2f}",
            "unpaid_count": unpaid_count
        }

    def _get_summary_for_teacher(self, teacher_id: UUID) -> dict[str, Any]:
        """Calculates and returns the financial summary for a teacher."""

        # 1. Fetch the per-parent balances for this teacher
        parent_balances = self.db.get_teacher_parent_balances(teacher_id)

        # 2. Calculate the total amount owed to the teacher
        # This is the sum of all negative balances (money owed by parents)
        total_owed_to_teacher = Decimal(0)
        # Calculate total credit held
        total_credit_held = Decimal(0)

        
        for item in parent_balances:
            balance = item.get('balance', Decimal(0))
            if balance < 0:
                # Sum of negative balances (money owed by parents)
                total_owed_to_teacher += -balance
            elif balance > 0:
                # NEW: Sum of positive balances (money paid in advance)
                total_credit_held += balance

        # 3. Fetch the count of lessons given this month
        lessons_this_month = self.db.count_teacher_logs_this_month(teacher_id)

        # 4. Return the formatted dictionary
        return {
            "total_owed_to_teacher": f"{total_owed_to_teacher:.2f}",
            "total_credit_held": f"{total_credit_held:.2f}", # Add the new field
            "total_lessons_given_this_month": lessons_this_month
        }

