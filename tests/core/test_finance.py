'''
testing the core finance system
'''
import pytest
from uuid import UUID
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
    all_logs = finance.get_tuition_logs_by_teacher(UUID('dcef54de-bc89-4388-a7a8-dba5d8327447'))
    print(f"Core Teacher Tuition Log Test.\nFound {len(all_logs)} logs.\nExample:")
    pprint(all_logs[0])

def test_finance_get_tuition_logs_by_parent(finance: Finance):
    all_logs = finance.get_tuition_logs_by_parent(UUID('d4c17e60-08de-47c7-9ef0-33ae8aa442fb'))
    print(f"Core Teacher Parent Log Test.\nFound {len(all_logs)} logs.\nExample:")

    pprint(all_logs[0])

def test_finance_get_tuition_logs_for_api(finance: Finance):
    all_logs = finance.get_tuition_logs_for_api(UUID('dcef54de-bc89-4388-a7a8-dba5d8327447'))
    print(f"Core Tuition Log API GET Response Test.\nFound {len(all_logs)} logs.\nExample:")
    pprint(all_logs[0])

