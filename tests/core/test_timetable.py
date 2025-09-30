'''
testing core/timetable.py
'''
from efficient_tutor_backend.core.timetable import TimeTable

from pprint import pprint

def test_timetable_initialization(timetable: TimeTable):
    """
    Tests if the TimeTable service can be instantiated correctly.
    """
    assert timetable is not None
    assert timetable.db is not None
    assert timetable.tuitions_service is not None

def test_timetable_get_latest_scheduled_tuitions(timetable: TimeTable):
    all_scheduled_tuitions = timetable.get_latest_scheduled_tuitions()
    print(f"No. Timetable Tuitions: {len(all_scheduled_tuitions)}")
    print(all_scheduled_tuitions[0])
    print(repr(all_scheduled_tuitions[0]))


def test_timetable_get_latest_for_api(timetable: TimeTable):
    latest_for_api = timetable.get_latest_for_api()
    print(f"No. Timetable Tuition: {len(latest_for_api)}")
    pprint(latest_for_api[0])

