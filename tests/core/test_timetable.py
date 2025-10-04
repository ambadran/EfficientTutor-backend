'''
testing core/timetable.py
'''
from tests.constants import TEST_PARENT_ID, TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_PARENT_IDS
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


def test_timetable_get_all_for_api_for_teacher(timetable: TimeTable):
    latest_for_api = timetable.get_all_for_api(TEST_TEACHER_ID)
    print(f"Got Timetable Tuition: {len(latest_for_api)} for teacher user.\nExample:\n")
    pprint(latest_for_api[0])

def test_timetable_get_all_for_api_for_parent(timetable: TimeTable):
    latest_for_api = timetable.get_all_for_api(TEST_PARENT_ID)
    print(f"Got Timetable Tuition: {len(latest_for_api)} for parent user.\nExample:\n")
    pprint(latest_for_api[0])

def test_timetable_get_all_for_api_for_student(timetable: TimeTable):
    latest_for_api = timetable.get_all_for_api(TEST_STUDENT_ID)
    print(f"Got Timetable Tuition: {len(latest_for_api)} for student user.\nExample:\n")
    pprint(latest_for_api[0])

