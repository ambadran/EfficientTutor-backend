"""
Test data for various log types: TuitionLogs, TuitionLogCharges, and PaymentLogs.
"""
from tests.constants import (
    TEST_TUITION_LOG_ID_SCHEDULED, TEST_TUITION_LOG_ID_CUSTOM, 
    TEST_TUITION_LOG_ID_UNRELATED_TEACHER,
    TEST_TUITION_LOG_ID_SAME_TEACHER_DIFF_PARENT,
    TEST_TUITION_LOG_ID_SAME_PARENT_DIFF_TEACHER,
    TEST_PAYMENT_LOG_ID,
    TEST_PAYMENT_LOG_ID_UNRELATED,
    TEST_PAYMENT_LOG_ID_SAME_TEACHER_DIFF_PARENT,
    TEST_PAYMENT_LOG_ID_SAME_PARENT_DIFF_TEACHER,
    TEST_TUITION_ID, TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_PARENT_ID,
    TEST_UNRELATED_TEACHER_ID, TEST_UNRELATED_PARENT_ID, TEST_UNRELATED_STUDENT_ID,
    FIN_TEACHER_A_ID, FIN_TEACHER_B_ID,
    FIN_PARENT_A_ID, FIN_PARENT_B_ID,
    FIN_STUDENT_A1_ID, FIN_STUDENT_A2_ID, FIN_STUDENT_B1_ID,
    FIN_LOG_1_ID, FIN_LOG_2_ID, FIN_LOG_3_ID, FIN_LOG_4_ID, FIN_LOG_5_ID,
    FIN_PAY_1_ID, FIN_PAY_2_ID
)
from src.efficient_tutor_backend.database.db_enums import TuitionLogCreateTypeEnum, EducationalSystemEnum
from datetime import datetime, timezone, timedelta

# --- Dynamic Dates ---
NOW = datetime.now(timezone.utc)
LAST_MONTH = NOW - timedelta(days=40) # Ensure it's clearly in the past month

# --- Tuition Logs ---
TUITION_LOGS_DATA = [
    {
        "factory": "RawTuitionLogFactory",
        "id": TEST_TUITION_LOG_ID_SCHEDULED,
        "create_type": TuitionLogCreateTypeEnum.SCHEDULED.value,
        "tuition_id": TEST_TUITION_ID,
        "teacher_id": TEST_TEACHER_ID,
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    {
        "factory": "RawTuitionLogFactory",
        "id": TEST_TUITION_LOG_ID_CUSTOM,
        "create_type": TuitionLogCreateTypeEnum.CUSTOM.value,
        "tuition_id": TEST_TUITION_ID,
        "teacher_id": TEST_TEACHER_ID,
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    # --- New Logs for Filtering Tests ---
    {
        # Completely unrelated log (Different Teacher, Different Parent/Student)
        "factory": "RawTuitionLogFactory",
        "id": TEST_TUITION_LOG_ID_UNRELATED_TEACHER,
        "create_type": TuitionLogCreateTypeEnum.CUSTOM.value,
        "teacher_id": TEST_UNRELATED_TEACHER_ID,
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    {
        # Same Teacher, Different Parent/Student
        "factory": "RawTuitionLogFactory",
        "id": TEST_TUITION_LOG_ID_SAME_TEACHER_DIFF_PARENT,
        "create_type": TuitionLogCreateTypeEnum.CUSTOM.value,
        "teacher_id": TEST_TEACHER_ID,
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    {
        # Different Teacher, Same Parent/Student
        "factory": "RawTuitionLogFactory",
        "id": TEST_TUITION_LOG_ID_SAME_PARENT_DIFF_TEACHER,
        "create_type": TuitionLogCreateTypeEnum.CUSTOM.value,
        "teacher_id": TEST_UNRELATED_TEACHER_ID,
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    # --- Financial Sandbox Logs ---
    {
        # T_A -> S_A1 ($100). Old.
        "factory": "RawTuitionLogFactory",
        "id": FIN_LOG_1_ID,
        "teacher_id": FIN_TEACHER_A_ID,
        "start_time": LAST_MONTH,
        "end_time": LAST_MONTH + timedelta(hours=1),
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    {
        # T_A -> S_A2 ($50). Old.
        "factory": "RawTuitionLogFactory",
        "id": FIN_LOG_2_ID,
        "teacher_id": FIN_TEACHER_A_ID,
        "start_time": LAST_MONTH,
        "end_time": LAST_MONTH + timedelta(hours=1),
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    {
        # T_A -> S_A1 ($100). Current.
        "factory": "RawTuitionLogFactory",
        "id": FIN_LOG_3_ID,
        "teacher_id": FIN_TEACHER_A_ID,
        "start_time": NOW,
        "end_time": NOW + timedelta(hours=1),
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    {
        # T_A -> S_B1 ($50). Current.
        "factory": "RawTuitionLogFactory",
        "id": FIN_LOG_4_ID,
        "teacher_id": FIN_TEACHER_A_ID,
        "start_time": NOW,
        "end_time": NOW + timedelta(hours=1),
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    {
        # T_B -> S_A1 ($200). Current.
        "factory": "RawTuitionLogFactory",
        "id": FIN_LOG_5_ID,
        "teacher_id": FIN_TEACHER_B_ID,
        "start_time": NOW,
        "end_time": NOW + timedelta(hours=1),
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
]

# --- Tuition Log Charges ---
TUITION_LOG_CHARGES_DATA = [
    {
        "factory": "RawTuitionLogChargeFactory",
        "tuition_log_id": TEST_TUITION_LOG_ID_SCHEDULED,
        "student_id": TEST_STUDENT_ID,
        "parent_id": TEST_PARENT_ID,
    },
    {
        "factory": "RawTuitionLogChargeFactory",
        "tuition_log_id": TEST_TUITION_LOG_ID_CUSTOM,
        "student_id": TEST_STUDENT_ID,
        "parent_id": TEST_PARENT_ID,
    },
    # --- Charges for New Filtering Logs ---
    {
        "factory": "RawTuitionLogChargeFactory",
        "tuition_log_id": TEST_TUITION_LOG_ID_UNRELATED_TEACHER,
        "student_id": TEST_UNRELATED_STUDENT_ID,
        "parent_id": TEST_UNRELATED_PARENT_ID,
    },
    {
        "factory": "RawTuitionLogChargeFactory",
        "tuition_log_id": TEST_TUITION_LOG_ID_SAME_TEACHER_DIFF_PARENT,
        "student_id": TEST_UNRELATED_STUDENT_ID,
        "parent_id": TEST_UNRELATED_PARENT_ID,
    },
    {
        "factory": "RawTuitionLogChargeFactory",
        "tuition_log_id": TEST_TUITION_LOG_ID_SAME_PARENT_DIFF_TEACHER,
        "student_id": TEST_STUDENT_ID,
        "parent_id": TEST_PARENT_ID,
    },
    # --- Charges for Financial Sandbox ---
    {
        # Log 1: T_A -> S_A1 ($100)
        "factory": "RawTuitionLogChargeFactory",
        "tuition_log_id": FIN_LOG_1_ID,
        "student_id": FIN_STUDENT_A1_ID,
        "parent_id": FIN_PARENT_A_ID,
        "cost": 100.00
    },
    {
        # Log 2: T_A -> S_A2 ($50)
        "factory": "RawTuitionLogChargeFactory",
        "tuition_log_id": FIN_LOG_2_ID,
        "student_id": FIN_STUDENT_A2_ID,
        "parent_id": FIN_PARENT_A_ID,
        "cost": 50.00
    },
    {
        # Log 3: T_A -> S_A1 ($100)
        "factory": "RawTuitionLogChargeFactory",
        "tuition_log_id": FIN_LOG_3_ID,
        "student_id": FIN_STUDENT_A1_ID,
        "parent_id": FIN_PARENT_A_ID,
        "cost": 100.00
    },
    {
        # Log 4: T_A -> S_B1 ($50)
        "factory": "RawTuitionLogChargeFactory",
        "tuition_log_id": FIN_LOG_4_ID,
        "student_id": FIN_STUDENT_B1_ID,
        "parent_id": FIN_PARENT_B_ID,
        "cost": 50.00
    },
    {
        # Log 5: T_B -> S_A1 ($200)
        "factory": "RawTuitionLogChargeFactory",
        "tuition_log_id": FIN_LOG_5_ID,
        "student_id": FIN_STUDENT_A1_ID,
        "parent_id": FIN_PARENT_A_ID,
        "cost": 200.00
    },
]

# --- Payment Logs ---
PAYMENT_LOGS_DATA = [
    {
        "factory": "RawPaymentLogFactory",
        "id": TEST_PAYMENT_LOG_ID,
        "parent_id": TEST_PARENT_ID,
        "teacher_id": TEST_TEACHER_ID,
    },
    {
        "factory": "RawPaymentLogFactory",
        "id": TEST_PAYMENT_LOG_ID_UNRELATED,
        "parent_id": TEST_UNRELATED_PARENT_ID,
        "teacher_id": TEST_UNRELATED_TEACHER_ID,
    },
    {
        "factory": "RawPaymentLogFactory",
        "id": TEST_PAYMENT_LOG_ID_SAME_TEACHER_DIFF_PARENT,
        "parent_id": TEST_UNRELATED_PARENT_ID,
        "teacher_id": TEST_TEACHER_ID,
    },
    {
        "factory": "RawPaymentLogFactory",
        "id": TEST_PAYMENT_LOG_ID_SAME_PARENT_DIFF_TEACHER,
        "parent_id": TEST_PARENT_ID,
        "teacher_id": TEST_UNRELATED_TEACHER_ID,
    },
    # --- Financial Sandbox Payments ---
    {
        # Pay 1: P_A -> T_A ($120)
        "factory": "RawPaymentLogFactory",
        "id": FIN_PAY_1_ID,
        "parent_id": FIN_PARENT_A_ID,
        "teacher_id": FIN_TEACHER_A_ID,
        "amount_paid": 120.00,
        "payment_date": NOW
    },
    {
        # Pay 2: P_B -> T_A ($60)
        "factory": "RawPaymentLogFactory",
        "id": FIN_PAY_2_ID,
        "parent_id": FIN_PARENT_B_ID,
        "teacher_id": FIN_TEACHER_A_ID,
        "amount_paid": 60.00,
        "payment_date": NOW
    }
]