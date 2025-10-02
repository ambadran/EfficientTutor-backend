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
    print(f"Found {len(all_tuitions)} Tuitions\nExample:")
    pprint(all_tuitions[0])

def test_db_get_tuition_logs_by_teacher(db_handler: DatabaseHandler):
    raw_logs = db_handler.get_tuition_logs_by_teacher(UUID('dcef54de-bc89-4388-a7a8-dba5d8327447'))
    print(f"Found: {len(raw_logs)} Tuition Logs for Teacher User.\nExample:")
    pprint(raw_logs[0])

def test_db_get_tuition_logs_by_parent(db_handler: DatabaseHandler):
    raw_logs = db_handler.get_tuition_logs_by_parent(UUID('d4c17e60-08de-47c7-9ef0-33ae8aa442fb'))
    print(f"Found: {len(raw_logs)} Tuition Logs for parent User.\nExample:")
    pprint(raw_logs[0])

def test_db_get_parend_ids_for_teacher(db_handler: DatabaseHandler):
    parent_ids = db_handler.get_parent_ids_for_teacher(UUID('dcef54de-bc89-4388-a7a8-dba5d8327447'))
    print(f"Found: {len(parent_ids)} parents related to this teacher.")
    pprint(parent_ids)

def test_db_get_users_by_ids(db_handler: DatabaseHandler):
    parent_users_ids = [UUID('e850ce9b-d934-47b9-a029-b510f39d5bbc'),
                         UUID('d4c17e60-08de-47c7-9ef0-33ae8aa442fb'),
                         UUID('7accbce5-4cdd-4ca3-930f-b0042e035299'),
                         UUID('a6934e55-9538-4c06-a7b0-545fbd4d8cee'),
                         UUID('eca287cc-2774-43d6-bef8-8f2d75ad11cf')]
    hydrated_users = db_handler.get_users_by_ids(parent_users_ids)
    pprint(hydrated_users)






