'''
testing all the /tuition-logs endpoints
'''
import pytest

from tests.constants import *
from efficient_tutor_backend.core.finance import Finance

from pprint import pp as pprint

def test_get_all_tuition_logs(client):

    # -- Testing Teacher User
    response = client.get(f'/tuition-logs?viewer_id={TEST_TEACHER_ID}')

    print(f"\n=== GET /tuition-logs? Teacher ID RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Got {len(response.get_json())} logs for teacher user\nExamples:\n")
    found_custom = False
    found_scheduled = False
    for example_log in response.get_json():
        if example_log['create_type'] == 'CUSTOM' and not found_custom:
            print("CUSTOM Type response:")
            pprint(example_log)
            found_custom = True
        elif example_log['create_type'] == 'SCHEDULED' and not found_scheduled:
            print("SCHEDULED Type response:")
            pprint(example_log)
            found_scheduled = True
    print("===================================\n")

    assert response.status_code == 200
    assert isinstance(response.get_json(), list)

    # -- Testing Parent user
    response = client.get(f'/tuition-logs?viewer_id={TEST_PARENT_ID}')

    print(f"\n=== GET /tuition-logs? Parent ID RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Got {len(response.get_json())} logs for parent user\nExample:\n")
    pprint(response.get_json()[0])
    print("===================================\n")

    assert response.status_code == 200
    assert isinstance(response.get_json(), list)

    # -- Testing Student user
    response = client.get(f'/tuition-logs?viewer_id={TEST_STUDENT_ID}')

    print(f"\n=== GET /tuition-logs? Student ID RESPONSE ===")
    print(f"Status Code: {response.status_code}, should be 403, forbidden/unauthorized")
    print(f"Response JSON:")
    pprint(response)
    print("===================================\n")

    assert response.status_code == 403


def test_post_scheduled_tuition_log(client, finance: Finance):
    """Tests creating a tuition log from a scheduled tuition."""
    # 1. Arrange: Prepare the test data
    payload = {
        "log_type": "scheduled",
        "tuition_id": "20f17bda-b529-48f6-b7c8-127f168aaf3c", # Assumes this tuition exists in your test DB
        "start_time": "2025-09-20T10:30:00.000Z",
        "end_time": "2025-09-20T12:00:00.000Z"
    }

    # 2. Act: Send the POST request
    response = client.post('/tuition-logs', json=payload)

    # 3. Assert: Verify the response and the database state
    assert response.status_code == 201  # 201 Created is the standard for successful POSTs

    response_data = response.get_json()
    pprint(response_data)
    assert 'id' in response_data['log_data']
    assert response_data['log_data']['create_type'] == 'SCHEDULED'

    # Verify that the log was actually created in the database
    db_log = finance.db.get_tuition_log_by_id(response_data['log_data']['id'])
    print(db_log.keys())
    assert db_log is not None
    assert str(db_log['tuition_id']) == payload['tuition_id']


def test_post_custom_tuition_log(client, finance: Finance):
    """Tests creating a custom tuition log from scratch."""
    # 1. Arrange: Prepare the test data
    payload = {
        "log_type": "custom",
        "teacher_id": str(TEST_TEACHER_ID),
        "subject": "Physics",
        "lesson_index": 1,
        "start_time": "2025-10-06T04:43:00.000Z",
        "end_time": "2025-10-06T05:43:00.000Z",
        "charges": [
            {"student_id": str(TEST_STUDENT_ID_1), "cost": 3},
            {"student_id": str(TEST_STUDENT_ID_2), "cost": 4}
        ]
    }

    # 2. Act: Send the POST request
    response = client.post('/tuition-logs', json=payload)

    # 3. Assert: Verify the response and the database state
    assert response.status_code == 201

    response_data = response.get_json()
    assert 'id' in response_data
    assert response_data['create_type'] == 'CUSTOM'
    assert response_data['subject'] == 'Physics'

    # Verify that the log was actually created in the database
    db_log = finance.db.get_tuition_log_by_id(response_data['id'])
    assert db_log is not None
    assert str(db_log['teacher_id']) == payload['teacher_id']
    
    # Also verify the charges were created correctly
    db_charges = finance.db.get_charges_for_log(response_data['id'])
    assert len(db_charges) == 2

def test_void_tuition_log(client, finance: Finance):
    """Tests voiding an existing tuition log."""
    # 1. Arrange: Create a log to be voided
    initial_payload = {
        "log_type": "custom",
        "teacher_id": str(TEST_TEACHER_ID),
        "subject": "History",
        "start_time": "2025-10-06T10:00:00.000Z",
        "end_time": "2025-10-06T11:00:00.000Z",
        "charges": [{"student_id": str(TEST_STUDENT_ID_1), "cost": 10}]
    }
    create_response = client.post('/tuition-logs', json=initial_payload)
    assert create_response.status_code == 201
    log_to_void_id = create_response.get_json()['id']

    # 2. Act: Call the void endpoint
    void_response = client.post(f'/tuition-logs/{log_to_void_id}/void')

    # 3. Assert: Check the response and verify the database state
    assert void_response.status_code == 200
    assert void_response.get_json()['message'] == f"Log {log_to_void_id} has been voided"

    # Verify the log's status in the database is now 'VOIDED'
    db_log = finance.db.get_tuition_log_by_id(log_to_void_id)
    assert db_log['status'] == 'VOIDED'


def test_correct_tuition_log(client, finance: Finance):
    """Tests correcting an existing tuition log."""
    # 1. Arrange: Create an initial log
    initial_payload = {
        "log_type": "custom",
        "teacher_id": str(TEST_TEACHER_ID),
        "subject": "Math",
        "start_time": "2025-10-07T14:00:00.000Z",
        "end_time": "2025-10-07T15:00:00.000Z",
        "charges": [{"student_id": str(TEST_STUDENT_ID_1), "cost": 20}]
    }
    create_response = client.post('/tuition-logs', json=initial_payload)
    assert create_response.status_code == 201
    original_log_id = create_response.get_json()['id']

    # Create the correction data
    correction_payload = {
        "start_time": "2025-10-07T14:05:00.000Z", # Corrected start time
        "end_time": "2025-10-07T15:05:00.000Z",   # Corrected end time
        "charges": [{"student_id": str(TEST_STUDENT_ID_1), "cost": 25}] # Corrected cost
    }

    # 2. Act: Call the correction endpoint
    correction_response = client.post(f'/tuition-logs/{original_log_id}/correction', json=correction_payload)

    # 3. Assert: Check the response and the database state
    assert correction_response.status_code == 200
    response_data = correction_response.get_json()
    new_log_id = response_data['new_log_id']
    assert response_data['original_log_id'] == original_log_id

    # Verify the original log is now voided and linked to the new one
    original_db_log = finance.db.get_tuition_log_by_id(original_log_id)
    assert original_db_log['status'] == 'VOIDED'
    assert str(original_db_log['corrected_to_log_id']) == new_log_id

    # Verify the new log has the corrected data and is linked to the old one
    new_db_log = finance.db.get_tuition_log_by_id(new_log_id)
    assert new_db_log is not None
    assert new_db_log['status'] == 'ACTIVE'
    assert str(new_db_log['corrected_from_log_id']) == original_log_id
    
    new_db_charges = finance.db.get_charges_for_log(new_log_id)
    assert new_db_charges[0]['cost'] == 25
