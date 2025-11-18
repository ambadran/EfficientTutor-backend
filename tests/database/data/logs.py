"""
Test data for various log types: TuitionLogs, TuitionLogCharges, and PaymentLogs.
"""
from tests.constants import (
    TEST_TUITION_LOG_ID_SCHEDULED, TEST_TUITION_LOG_ID_CUSTOM, TEST_PAYMENT_LOG_ID,
    TEST_TUITION_ID, TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_PARENT_ID
)
from src.efficient_tutor_backend.database.db_enums import TuitionLogCreateTypeEnum

LOGS_DATA = [
    # --- Tuition Logs ---
    {
        "factory": "TuitionLogFactory",
        "id": TEST_TUITION_LOG_ID_SCHEDULED,
        "create_type": TuitionLogCreateTypeEnum.SCHEDULED.value,
        "tuition_id": TEST_TUITION_ID,
        "teacher_id": TEST_TEACHER_ID,
    },
    {
        "factory": "TuitionLogFactory",
        "id": TEST_TUITION_LOG_ID_CUSTOM,
        "create_type": TuitionLogCreateTypeEnum.CUSTOM.value,
        "tuition_id": TEST_TUITION_ID,
        "teacher_id": TEST_TEACHER_ID,
    },
    # --- Tuition Log Charges (dependent on TuitionLogs) ---
    {
        "factory": "TuitionLogChargeFactory",
        "tuition_log_id": TEST_TUITION_LOG_ID_SCHEDULED,
        "student_id": TEST_STUDENT_ID,
        "parent_id": TEST_PARENT_ID,
    },
    {
        "factory": "TuitionLogChargeFactory",
        "tuition_log_id": TEST_TUITION_LOG_ID_CUSTOM,
        "student_id": TEST_STUDENT_ID,
        "parent_id": TEST_PARENT_ID,
    },
    # --- Payment Logs ---
    {
        "factory": "PaymentLogFactory",
        "id": TEST_PAYMENT_LOG_ID,
        "parent_id": TEST_PARENT_ID,
        "teacher_id": TEST_TEACHER_ID,
    },
]
