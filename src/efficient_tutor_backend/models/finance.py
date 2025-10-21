'''

'''
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



