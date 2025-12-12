"""
Test data for Timetable Runs, using the new relational structure.
"""
import datetime
from tests.constants import (
    TEST_TIMETABLE_RUN_ID,
    TEST_USER_SOLUTION_ID, # Student's solution
    TEST_USER_SOLUTION_TEACHER_ID,
    TEST_USER_SOLUTION_UNRELATED_STUDENT_ID,
    
    TEST_STUDENT_ID,
    TEST_TEACHER_ID,
    TEST_UNRELATED_STUDENT_ID,
    TEST_UNRELATED_TEACHER_ID,

    TEST_TUITION_ID,
    TEST_TUITION_ID_NO_LINK,
    TEST_TUITION_ID_UNRELATED,
    TEST_AVAILABILITY_INTERVAL_ID_TEACHER,

    TEST_SLOT_ID_STUDENT_MATH,
    TEST_SLOT_ID_STUDENT_PHYSICS,
    TEST_SLOT_ID_TEACHER_MATH,
    TEST_SLOT_ID_TEACHER_PHYSICS,
    TEST_SLOT_ID_TEACHER_AVAILABILITY,
    TEST_SLOT_ID_UNRELATED_CHEMISTRY
)

# --- 1. User Solutions ---
TIMETABLE_RUN_USER_SOLUTIONS_DATA = [
    # Main Student Solution
    {
        "factory": "TimetableRunUserSolutionFactory",
        "id": TEST_USER_SOLUTION_ID,
        "timetable_run_id": TEST_TIMETABLE_RUN_ID,
        "user_id": TEST_STUDENT_ID
    },
    # Main Teacher Solution
    {
        "factory": "TimetableRunUserSolutionFactory",
        "id": TEST_USER_SOLUTION_TEACHER_ID,
        "timetable_run_id": TEST_TIMETABLE_RUN_ID,
        "user_id": TEST_TEACHER_ID
    },
    # Unrelated Student Solution
    {
        "factory": "TimetableRunUserSolutionFactory",
        "id": TEST_USER_SOLUTION_UNRELATED_STUDENT_ID,
        "timetable_run_id": TEST_TIMETABLE_RUN_ID,
        "user_id": TEST_UNRELATED_STUDENT_ID
    }
]

# --- 2. Solution Slots ---
TIMETABLE_SOLUTION_SLOTS_DATA = [
    # --- Student Slots ---
    {
        "factory": "TimetableSolutionSlotFactory",
        "id": TEST_SLOT_ID_STUDENT_MATH,
        "solution_id": TEST_USER_SOLUTION_ID,
        "name": "Math Session",
        "day_of_week": 1, # Monday
        "start_time": datetime.time(10, 0),
        "end_time": datetime.time(11, 0),
        "tuition_id": TEST_TUITION_ID,
        "participant_ids": [TEST_TEACHER_ID, TEST_STUDENT_ID]
    },
    {
        "factory": "TimetableSolutionSlotFactory",
        "id": TEST_SLOT_ID_STUDENT_PHYSICS,
        "solution_id": TEST_USER_SOLUTION_ID,
        "name": "Physics Session",
        "day_of_week": 2, # Tuesday
        "start_time": datetime.time(14, 0),
        "end_time": datetime.time(15, 0),
        "tuition_id": TEST_TUITION_ID_NO_LINK,
        "participant_ids": [TEST_TEACHER_ID, TEST_STUDENT_ID]
    },

    # --- Teacher Slots (Mirroring Student + Availability) ---
    {
        "factory": "TimetableSolutionSlotFactory",
        "id": TEST_SLOT_ID_TEACHER_MATH,
        "solution_id": TEST_USER_SOLUTION_TEACHER_ID,
        "name": "Math with Test Student",
        "day_of_week": 1, # Monday
        "start_time": datetime.time(10, 0),
        "end_time": datetime.time(11, 0),
        "tuition_id": TEST_TUITION_ID,
        "participant_ids": [TEST_TEACHER_ID, TEST_STUDENT_ID]
    },
    {
        "factory": "TimetableSolutionSlotFactory",
        "id": TEST_SLOT_ID_TEACHER_PHYSICS,
        "solution_id": TEST_USER_SOLUTION_TEACHER_ID,
        "name": "Physics with Test Student",
        "day_of_week": 2, # Tuesday
        "start_time": datetime.time(14, 0),
        "end_time": datetime.time(15, 0),
        "tuition_id": TEST_TUITION_ID_NO_LINK,
        "participant_ids": [TEST_TEACHER_ID, TEST_STUDENT_ID]
    },
    {
        "factory": "TimetableSolutionSlotFactory",
        "id": TEST_SLOT_ID_TEACHER_AVAILABILITY,
        "solution_id": TEST_USER_SOLUTION_TEACHER_ID,
        "name": "Work",
        "day_of_week": 3, # Wednesday
        "start_time": datetime.time(9, 0),
        "end_time": datetime.time(17, 0),
        "availability_interval_id": TEST_AVAILABILITY_INTERVAL_ID_TEACHER,
        "participant_ids": [TEST_TEACHER_ID]
    },

    # --- Unrelated Student Slots ---
    {
        "factory": "TimetableSolutionSlotFactory",
        "id": TEST_SLOT_ID_UNRELATED_CHEMISTRY,
        "solution_id": TEST_USER_SOLUTION_UNRELATED_STUDENT_ID,
        "name": "Chemistry Session",
        "day_of_week": 5, # Friday
        "start_time": datetime.time(10, 0),
        "end_time": datetime.time(11, 0),
        "tuition_id": TEST_TUITION_ID_UNRELATED,
        # This tuition is with UNRELATED_TEACHER and UNRELATED_STUDENT
        "participant_ids": [TEST_UNRELATED_TEACHER_ID, TEST_UNRELATED_STUDENT_ID]
    }
]
