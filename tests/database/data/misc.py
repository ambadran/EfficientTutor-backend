"""
Test data for miscellaneous objects like Notes and TimetableRuns.
"""
import datetime
from tests.constants import TEST_NOTE_ID, TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_TUITION_ID

MISC_DATA = [
    # --- Notes ---
    {
        "factory": "NoteFactory",
        "id": TEST_NOTE_ID,
        "teacher_id": TEST_TEACHER_ID,
        "student_id": TEST_STUDENT_ID,
    },
    # --- Timetable Runs ---
    # This is more complex as it involves dynamic data (current time)
    # We can handle this by passing a callable or generating it in the seeder.
    # For now, we will define the static parts.
    {
        "factory": "TimetableRunFactory",
        # The solution_data will be generated dynamically in the seeder
    },
]
