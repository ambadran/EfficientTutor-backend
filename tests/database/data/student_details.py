"""
Test data for student-specific details like subjects and availability.
"""
from tests.constants import TEST_STUDENT_ID, TEST_TEACHER_ID
from src.efficient_tutor_backend.database.db_enums import SubjectEnum, AvailabilityTypeEnum, EducationalSystemEnum
from datetime import time

STUDENT_DETAILS_DATA = [
    {
        "factory": "StudentSubjectFactory",
        "student_id": TEST_STUDENT_ID,
        "teacher_id": TEST_TEACHER_ID,
        "subject": SubjectEnum.PHYSICS.value,
        "educational_system": EducationalSystemEnum.IGCSE.value,
    },
    {
        "factory": "StudentAvailabilityIntervalFactory",
        "student_id": TEST_STUDENT_ID,
        "day_of_week": 1,
        "start_time": time(9, 0),
        "end_time": time(17, 0),
        "availability_type": AvailabilityTypeEnum.SCHOOL.value,
    },
]
