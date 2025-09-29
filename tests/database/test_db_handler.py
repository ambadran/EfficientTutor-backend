'''
testing db_handler methods
'''
import pytest
import json
# from efficient_tutor_backend.database.db_handler import DatabaseHandler
from efficient_tutor_backend.database.db_handler2 import DatabaseHandler

from pprint import pp as pprint

def test_db_get_all_tuition_logs(db_handler: DatabaseHandler):
    all_tuition_logs = db_handler.get_all_tuition_logs('dcef54de-bc89-4388-a7a8-dba5d8327447')
    pprint(all_tuition_logs)

def test_db_get_all_users_by_role_parents(db_handler: DatabaseHandler):
    all_parents_data = db_handler.get_all_users_by_role('parent')
    pprint(all_parents_data)

def test_db_get_all_tuitions(db_handler: DatabaseHandler):
    all_tuitions = db_handler.get_all_tuitions()
    pprint(all_tuitions)
