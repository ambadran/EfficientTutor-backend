'''
This files handles all the finance logic
'''
from datetime import datetime, timedelta
from enum import Enum, auto
import uuid
from ..common.logger import log

class TuitionLogType(Enum):
    SCHEDULED = auto()
    CUSTOM = auto()

class LogbookService:
    """
    Handles the business logic for creating, voiding, and correcting
    tuition and payment logs.
    """
    def __init__(self, db_handler):
        self.db = db_handler

    def create_tuition_log(self, log_data: dict):
        """
        Main entry point for creating a new tuition log. It validates the data
        and orchestrates the creation of either a scheduled or manual log.
        """

        log_type = log_data.get('log_type')
        start_time_str = log_data.get('start_time')
        end_time_str = log_data.get('end_time')

        if not all([log_type, start_time_str, end_time_str]):
            raise ValueError("Missing required fields: log_type, start_time, or end_time.")

        # Basic time validation
        #TODO: put the defualt +2 hour
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
        if start_time >= end_time:
            raise ValueError("End time must be after start time.")

        if log_type == TuitionLogType.SCHEDULED.name.lower():
            prepared_log = self._prepare_scheduled_log(log_data)

        elif log_type == TuitionLogType.CUSTOM.name.lower():
            prepared_log = self._prepare_custom_log(log_data)

        else:
            raise ValueError(f"Invalid log_type: '{log_type}'. Must be 'SCHEDULED' or 'CUSTOM'.")
            
        new_log_id = self.db.insert_tuition_log(prepared_log)
        print(f"Successfully created tuition log with ID: {new_log_id}")
        return new_log_id

    def _prepare_scheduled_log(self, data):
        """Hydrates and validates data for a log created from a pre-defined tuition."""
        tuition_id = data.get('tuition_id')
        if not tuition_id:
            raise ValueError("tuition_id is required for a 'scheduled' log.")

        tuition_details = self.db.get_tuition_details_by_id(tuition_id)
        if not tuition_details:
            raise ValueError(f"Tuition with ID '{tuition_id}' not found.")

        # Parse the student_ids string from the database into a proper list
        raw_ids = tuition_details.get('student_ids')
        if isinstance(raw_ids, str):
            student_ids = raw_ids.strip('{}').split(',')
        else:
            student_ids = raw_ids or []
        
        if not student_ids:
            raise ValueError("Tuition details do not contain any student IDs.")
        
        parent_user_id = self.db.get_parent_id_for_student(student_ids[0])
        attendee_names = self.db.get_student_names_by_ids(student_ids)

        return {
            "id": str(uuid.uuid4()),
            "create_type": TuitionLogType.SCHEDULED.name,
            "tuition_id": tuition_id,
            "parent_user_id": parent_user_id,
            "subject": tuition_details['subject'],
            "attendee_names": attendee_names,
            "lesson_index": tuition_details['lesson_index'],
            "cost": tuition_details['cost'],
            "start_time": data['start_time'],
            "end_time": data['end_time']
        }

    def _prepare_custom_log(self, data):
        """Validates and prepares data for a manually entered log."""
        student_ids = data.get('student_ids')
        if not student_ids or not isinstance(student_ids, list):
            raise ValueError("A non-empty list of student_ids is required for a 'manual' log.")
            
        parent_user_id = self.db.get_parent_id_for_student(student_ids[0])
        # In a real system, you might verify all students belong to the same parent.
        
        attendee_names = self.db.get_student_names_by_ids(student_ids)
        if len(attendee_names) != len(student_ids):
            raise ValueError("One or more student IDs are invalid.")

        return {
            "id": str(uuid.uuid4()),
            "create_type": TuitionLogType.CUSTOM.name,
            "parent_user_id": parent_user_id,
            "subject": data.get('subject'),
            "attendee_names": attendee_names,
            "cost": data.get('cost'),
            "start_time": data['start_time'],
            "end_time": data['end_time'],
            "tuition_id": None,
            "lesson_index": None
        }
        
    def perform_log_correction(self, original_log_id: str, correction_data: dict):
        """
        Atomically voids an old log and creates a new one with corrected data.
        """
        # 1. Void the original log
        success = self.db.void_tuition_log(original_log_id)
        if not success:
            raise ValueError(f"Could not find tuition log with ID: {original_log_id}")

        # 2. Create the new, corrected log
        new_log_id = self.create_tuition_log(correction_data)
        
        # 3. (Optional but good practice) Link the new log to the old one
        self.db.link_corrected_log(new_log_id, original_log_id)
        
        print(f"Successfully corrected log {original_log_id}. New log is {new_log_id}.")
        return new_log_id


class FinancialLedgerService:
    """
    Handles the business logic for calculating and generating financial reports
    for parents.
    """
    def __init__(self, db_handler):
        self.db = db_handler

    def generate_report(self, parent_user_id: str):
        """
        Generates a full financial report for a given parent, including a
        summary and a detailed list of all transactions.
        """
        # 1. Fetch all raw financial data from the database.
        tuition_logs = self.db.get_tuition_logs_for_parent(parent_user_id)
        payment_logs = self.db.get_payment_logs_for_parent(parent_user_id)

        # 2. Perform all calculations using the fetched data.
        return self._calculate_ledger(tuition_logs, payment_logs)

    def _calculate_ledger(self, tuition_logs: list, payment_logs: list):
        """
        The core calculation engine. Processes lists of tuitions and payments
        to determine financial status. This logic is completely decoupled
        from the database.
        """
        log.info(f"Calculating ledger for {len(tuition_logs)} tuition(s) and {len(payment_logs)} payment(s).")
        total_paid = sum(log['amount_paid'] for log in payment_logs)
        paid_balance = float(total_paid)
        
        unpaid_count = 0
        total_due = 0.0
        
        processed_logs = []

        for log_entry in tuition_logs:
            cost = float(log_entry['cost'])
            
            # --- NEW: Calculate duration and format times ---
            #TODO: add timezone
            start_time = log_entry['start_time'] + timedelta(hours=3)
            end_time = log_entry['end_time'] + timedelta(hours=3)
            duration_delta = end_time - start_time
            duration_hours = duration_delta.total_seconds() / 3600.0

            log_details = {
                "id": str(log_entry['id']),
                "subject": log_entry['subject'],
                "attendees": log_entry['attendee_names'],
                "date": start_time.strftime('%Y-%m-%d'),
                "start_time": start_time.strftime('%I:%M %p'),
                "end_time": end_time.strftime('%I:%M %p'),
                "duration": f"{duration_hours:.1f}h",
                "cost": cost
            }

            if paid_balance >= cost:
                log_details['status'] = 'Paid'
                paid_balance -= cost
            else:
                log_details['status'] = 'Unpaid'
                unpaid_count += 1
                total_due += cost
            
            processed_logs.append(log_details)
        
        summary = {
            "total_due": round(total_due, 2),
            "unpaid_count": unpaid_count,
            "credit_balance": round(paid_balance, 2)
        }
        
        log.info(f"Ledger calculation complete. Total Due: {summary['total_due']}, Credit: {summary['credit_balance']}")

        return {
            "summary": summary,
            "detailed_logs": processed_logs
        }
