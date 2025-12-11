"""
Test data for Timetable Runs, using the new relational structure.
"""
import datetime
from tests.constants import (
    TEST_TIMETABLE_RUN_ID,
    TEST_USER_SOLUTION_ID,
    TEST_SLOT_ID,
    TEST_STUDENT_ID,
    TEST_TEACHER_ID,
    TEST_TUITION_ID
)

# --- 1. User Solutions ---
# Links the Master Run (9999) to specific users.
TIMETABLE_RUN_USER_SOLUTIONS_DATA = [
    {
        "factory": "TimetableRunUserSolutionFactory",
        "id": TEST_USER_SOLUTION_ID,
        "timetable_run_id": TEST_TIMETABLE_RUN_ID,
        "user_id": TEST_STUDENT_ID
    }
]

# --- 2. Solution Slots ---
# The actual schedule entries for the user solutions.
# Note: start_time and end_time must be datetime.time objects for asyncpg.
TIMETABLE_SOLUTION_SLOTS_DATA = [
    {
        "factory": "TimetableSolutionSlotFactory",
        "id": TEST_SLOT_ID,
        "solution_id": TEST_USER_SOLUTION_ID,
        "name": "Math Session",
        "day_of_week": 1, # Monday
        "start_time": datetime.time(10, 0),
        "end_time": datetime.time(11, 0),
        "tuition_id": TEST_TUITION_ID,
        "participant_ids": [TEST_TEACHER_ID, TEST_STUDENT_ID]
    }
]