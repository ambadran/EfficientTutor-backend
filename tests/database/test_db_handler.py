'''
testing db_handler methods
'''
import pytest
import json
from efficient_tutor_backend.database.db_handler import DatabaseHandler

from pprint import pp as pprint

def test_db_get_all_tuition_logs(db_handler: DatabaseHandler):
    all_tuition_logs = db_handler.get_all_tuition_logs('dcef54de-bc89-4388-a7a8-dba5d8327447')
    pprint(all_tuition_logs)
