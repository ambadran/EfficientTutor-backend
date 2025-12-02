"""
Test data for Timetable Runs.
"""
import datetime
from tests.constants import TEST_TUITION_ID

# Calculate a dynamic timestamp relative to when this module is imported (seeding time)
# This replaces the dynamic logic previously in seed_test_db.py
now = datetime.datetime.now(datetime.timezone.utc)
solution_entry = {
    "category": "Tuition", 
    "id": str(TEST_TUITION_ID), 
    "start_time": now.isoformat(), 
    "end_time": (now + datetime.timedelta(hours=1)).isoformat()
}

# --- Timetable Runs ---
TIMETABLE_RUNS_DATA = [
    {
        "factory": "TimetableRunFactory",
        "solution_data": [solution_entry]
    },
]
