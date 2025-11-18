"""
Test data for Tuitions and their related objects like MeetingLinks 
and TuitionTemplateCharges.
"""
from tests.constants import (
    TEST_TUITION_ID, TEST_TUITION_ID_NO_LINK, TEST_TEACHER_ID,
    TEST_STUDENT_ID, TEST_PARENT_ID
)

# This list will be processed in order by the seeder.
# We define Tuitions first, then their dependent objects.
TUITIONS_DATA = [
    # --- Tuitions ---
    {
        "factory": "TuitionFactory",
        "id": TEST_TUITION_ID,
        "teacher_id": TEST_TEACHER_ID,
    },
    {
        "factory": "TuitionFactory",
        "id": TEST_TUITION_ID_NO_LINK,
        "teacher_id": TEST_TEACHER_ID,
    },
    # --- Meeting Links (dependent on Tuitions) ---
    {
        "factory": "MeetingLinkFactory",
        "tuition_id": TEST_TUITION_ID,
        "meeting_link_type": "GOOGLE_MEET",
        "meeting_link": "https://meet.google.com/abc-defg-hij",
        "meeting_id": "abc-defg-hij",
        "meeting_password": None,
    },
    # --- Template Charges (dependent on Tuitions, Students, Parents) ---
    {
        "factory": "TuitionTemplateChargeFactory",
        "tuition_id": TEST_TUITION_ID,
        "student_id": TEST_STUDENT_ID,
        "parent_id": TEST_PARENT_ID,
    },
    {
        "factory": "TuitionTemplateChargeFactory",
        "tuition_id": TEST_TUITION_ID_NO_LINK,
        "student_id": TEST_STUDENT_ID,
        "parent_id": TEST_PARENT_ID,
    },
]
