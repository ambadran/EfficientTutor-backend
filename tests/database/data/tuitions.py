"""
Test data for Tuitions and their related objects like MeetingLinks 
and TuitionTemplateCharges.
"""
from tests.constants import (
    TEST_TUITION_ID, TEST_TUITION_ID_NO_LINK, TEST_TUITION_ID_UNRELATED,
    TEST_TEACHER_ID, TEST_UNRELATED_TEACHER_ID,
    TEST_STUDENT_ID, TEST_PARENT_ID,
    FIN_TEACHER_A_ID, FIN_TEACHER_B_ID,
    FIN_PARENT_A_ID, FIN_PARENT_B_ID,
    FIN_STUDENT_A1_ID, FIN_STUDENT_A2_ID, FIN_STUDENT_B1_ID,
    FIN_TUITION_1_ID, FIN_TUITION_2_ID, FIN_TUITION_3_ID, FIN_TUITION_4_ID
)
from src.efficient_tutor_backend.database.db_enums import EducationalSystemEnum

# --- Tuitions ---
TUITIONS_DATA = [
    {
        "factory": "RawTuitionFactory",
        "id": TEST_TUITION_ID,
        "teacher_id": TEST_TEACHER_ID,
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    {
        "factory": "RawTuitionFactory",
        "id": TEST_TUITION_ID_NO_LINK,
        "teacher_id": TEST_TEACHER_ID,
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    {
        "factory": "RawTuitionFactory",
        "id": TEST_TUITION_ID_UNRELATED,
        "teacher_id": TEST_UNRELATED_TEACHER_ID,
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    # --- Financial Sandbox Tuitions ---
    {
        "factory": "RawTuitionFactory",
        "id": FIN_TUITION_1_ID,
        "teacher_id": FIN_TEACHER_A_ID,
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    {
        "factory": "RawTuitionFactory",
        "id": FIN_TUITION_2_ID,
        "teacher_id": FIN_TEACHER_A_ID,
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    {
        "factory": "RawTuitionFactory",
        "id": FIN_TUITION_3_ID,
        "teacher_id": FIN_TEACHER_A_ID,
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
    {
        "factory": "RawTuitionFactory",
        "id": FIN_TUITION_4_ID,
        "teacher_id": FIN_TEACHER_B_ID,
        "educational_system": EducationalSystemEnum.IGCSE.value,
        "grade": 10,
    },
]

# --- Meeting Links ---
MEETING_LINKS_DATA = [
    {
        "factory": "RawMeetingLinkFactory",
        "tuition_id": TEST_TUITION_ID,
        "meeting_link_type": "GOOGLE_MEET",
        "meeting_link": "https://meet.google.com/abc-defg-hij",
        "meeting_id": "abc-defg-hij",
        "meeting_password": None,
    },
]

# --- Template Charges ---
TUITION_TEMPLATE_CHARGES_DATA = [
    {
        "factory": "RawTuitionTemplateChargeFactory",
        "tuition_id": TEST_TUITION_ID,
        "student_id": TEST_STUDENT_ID,
        "parent_id": TEST_PARENT_ID,
    },
    {
        "factory": "RawTuitionTemplateChargeFactory",
        "tuition_id": TEST_TUITION_ID_NO_LINK,
        "student_id": TEST_STUDENT_ID,
        "parent_id": TEST_PARENT_ID,
    },
    # --- Financial Sandbox Charges ---
    {
        "factory": "RawTuitionTemplateChargeFactory",
        "tuition_id": FIN_TUITION_1_ID,
        "student_id": FIN_STUDENT_A1_ID,
        "parent_id": FIN_PARENT_A_ID,
    },
    {
        "factory": "RawTuitionTemplateChargeFactory",
        "tuition_id": FIN_TUITION_2_ID,
        "student_id": FIN_STUDENT_A2_ID,
        "parent_id": FIN_PARENT_A_ID,
    },
    {
        "factory": "RawTuitionTemplateChargeFactory",
        "tuition_id": FIN_TUITION_3_ID,
        "student_id": FIN_STUDENT_B1_ID,
        "parent_id": FIN_PARENT_B_ID,
    },
    {
        "factory": "RawTuitionTemplateChargeFactory",
        "tuition_id": FIN_TUITION_4_ID,
        "student_id": FIN_STUDENT_A1_ID,
        "parent_id": FIN_PARENT_A_ID,
    },
]
