"""
Test data for Tuitions and their related objects like MeetingLinks 
and TuitionTemplateCharges.
"""
from tests.constants import (
    TEST_TUITION_ID, TEST_TUITION_ID_NO_LINK, TEST_TEACHER_ID,
    TEST_STUDENT_ID, TEST_PARENT_ID
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
]
