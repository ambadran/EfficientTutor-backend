'''
testing db_handler methods
'''
import pytest
import json
from uuid import UUID
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
    pprint(all_tuitions)

def test_db_get_tuition_logs_by_teacher(db_handler: DatabaseHandler):
    raw_logs = db_handler.get_tuition_logs_by_teacher(UUID('dcef54de-bc89-4388-a7a8-dba5d8327447'))
    print(f"Found: {len(raw_logs)} Tuition Logs for Teacher User.\nExample:")
    pprint(raw_logs[0])

def test_db_get_tuition_logs_by_parent(db_handler: DatabaseHandler):
    raw_logs = db_handler.get_tuition_logs_by_parent(UUID('d4c17e60-08de-47c7-9ef0-33ae8aa442fb'))
    print(f"Found: {len(raw_logs)} Tuition Logs for parent User.\nExample:")
    pprint(raw_logs[0])

