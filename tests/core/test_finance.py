'''
testing the core finance system
'''
import pytest
from uuid import UUID
from tests.constants import *
from efficient_tutor_backend.core.finance import Finance

from pprint import pprint

def test_finance_initialization(finance: Finance):
    """
    Tests if the Finance service and its dependencies can be instantiated correctly.
    """
    assert finance is not None
    assert finance.db is not None
    assert finance.students_service is not None
    assert finance.parents_service is not None
    assert finance.tuitions_service is not None


def test_finance_get_tuition_logs_by_teacher(finance: Finance):
    all_logs = finance.get_tuition_logs_by_teacher(TEST_TEACHER_ID)
    print(f"Core Teacher Tuition Log Test.\nFound {len(all_logs)} logs.\nExample:")
    print(all_logs[3])
    print(repr(all_logs[3]))

def test_finance_get_tuition_logs_by_parent(finance: Finance):
    all_logs = finance.get_tuition_logs_by_parent(TEST_PARENT_ID)
    print(f"Core Teacher Parent Log Test.\nFound {len(all_logs)} logs.\nExample:")
    print(all_logs[0])
    print(repr(all_logs[0]))

def test_finance_get_tuition_logs_by_teacher_for_api(finance: Finance):
    all_logs = finance.get_tuition_logs_for_api(TEST_TEACHER_ID)
    print(f"Core Tuition Log API GET Response Test.\nFound {len(all_logs)} logs.\nExample:")
    found_custom = False
    found_scheduled = False
    for example_log in all_logs:
        if example_log['create_type'] == 'CUSTOM' and not found_custom:
            print("CUSTOM Type response:")
            pprint(example_log)
            found_custom = True
        elif example_log['create_type'] == 'SCHEDULED' and not found_scheduled:
            print("SCHEDULED Type response:")
            pprint(example_log)
            found_scheduled = True

def test_finance_get_tuition_logs_by_parent_for_api(finance: Finance):
    all_logs = finance.get_tuition_logs_for_api(TEST_PARENT_ID)
    print(f"Core Tuition Log API GET Response Test.\nFound {len(all_logs)} logs.\nExample:")
    pprint(all_logs)

