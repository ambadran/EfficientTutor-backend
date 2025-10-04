'''
testing db_handler methods
'''
import pytest
import json
from tests.constants import TEST_PARENT_ID, TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_PARENT_IDS
# from efficient_tutor_backend.database.db_handler import DatabaseHandler
from efficient_tutor_backend.database.db_handler2 import DatabaseHandler

from pprint import pp as pprint

# deprecated
# def test_db_get_all_tuition_logs(db_handler: DatabaseHandler):
#     all_tuition_logs = db_handler.get_all_tuition_logs('dcef54de-bc89-4388-a7a8-dba5d8327447')
#     pprint(all_tuition_logs)

def test_db_get_all_users_by_role_parents(db_handler: DatabaseHandler):
    all_parents_data = db_handler.get_all_users_by_role('parent')
    pprint(all_parents_data)

def test_db_check_tuition_data_integrity(db_handler: DatabaseHandler):
    pprint(db_handler.check_tuition_data_integrity())

def test_db_get_all_tuitions_raw(db_handler: DatabaseHandler):
    all_tuitions = db_handler.get_all_tuitions_raw()
    print(f"Found {len(all_tuitions)} Tuitions\nExample:")
    pprint(all_tuitions[0])

def test_db_get_tuition_logs_by_teacher(db_handler: DatabaseHandler):
    raw_logs = db_handler.get_tuition_logs_by_teacher(TEST_TEACHER_ID)
    print(f"Found: {len(raw_logs)} Tuition Logs for Teacher User.\nExample:")
    pprint(raw_logs[0])

def test_db_get_tuition_logs_by_parent(db_handler: DatabaseHandler):
    raw_logs = db_handler.get_tuition_logs_by_parent(TEST_PARENT_ID)
    print(f"Found: {len(raw_logs)} Tuition Logs for parent User.\nExample:")
    pprint(raw_logs[0])

def test_db_get_parend_ids_for_teacher(db_handler: DatabaseHandler):
    parent_ids = db_handler.get_parent_ids_for_teacher(TEST_TEACHER_ID)
    print(f"Found: {len(parent_ids)} parents related to this teacher.")
    pprint(parent_ids)

def test_db_get_users_by_ids(db_handler: DatabaseHandler):
    hydrated_users = db_handler.get_users_by_ids(TEST_PARENT_IDS)
    pprint(hydrated_users)


def test_db_get_all_tuitions_raw_for_teacher(db_handler: DatabaseHandler):
    teacher_tuitions = db_handler.get_all_tuitions_raw_for_teacher(TEST_TEACHER_ID)
    print(f"Found {len(teacher_tuitions)} Tuitions for {TEST_TEACHER_ID} teacher user.\nExample\n")
    pprint(teacher_tuitions[0])

def test_db_get_all_tuitions_raw_for_parent(db_handler: DatabaseHandler):
    parent_tuitions = db_handler.get_all_tuitions_raw_for_parent(TEST_PARENT_ID)
    print(f"Found {len(parent_tuitions)} Tuitions for {TEST_PARENT_ID} parent user.\nExample\n")
    pprint(parent_tuitions[0])

def test_db_get_all_tuitions_raw_for_student(db_handler: DatabaseHandler):
    student_tuitions = db_handler.get_all_tuitions_raw_for_student(TEST_STUDENT_ID)
    print(f"Found {len(student_tuitions)} Tuitions for {TEST_STUDENT_ID} student user.\nExample\n")
    pprint(student_tuitions[0])


