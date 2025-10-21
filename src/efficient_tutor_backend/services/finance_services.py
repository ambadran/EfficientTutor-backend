'''

'''
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

