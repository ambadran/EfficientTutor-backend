"""
Test data for teacher-specific details like availability.
"""
from tests.constants import TEST_TEACHER_ID, TEST_AVAILABILITY_INTERVAL_ID_TEACHER
from src.efficient_tutor_backend.database.db_enums import AvailabilityTypeEnum
from datetime import time

TEACHER_DETAILS_DATA = [
    {
        "factory": "RawAvailabilityIntervalFactory",
        "id": TEST_AVAILABILITY_INTERVAL_ID_TEACHER,
        "user_id": TEST_TEACHER_ID,
        "day_of_week": 2, # Tuesday
        "start_time": time(14, 0),
        "end_time": time(18, 0),
        "availability_type": AvailabilityTypeEnum.WORK.value,
    },
    {
        "factory": "RawAvailabilityIntervalFactory",
        "user_id": TEST_TEACHER_ID,
        "day_of_week": 4, # Thursday
        "start_time": time(10, 0),
        "end_time": time(12, 0),
        "availability_type": AvailabilityTypeEnum.PERSONAL.value,
    },
]
