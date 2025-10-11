'''
testing payment logs endpoints
'''
import pytest

from tests.constants import *
from efficient_tutor_backend.core.finance import Finance

from pprint import pp as pprint


def test_get_all_payment_logs(client):

    # -- Testing Teacher User
    response = client.get(f'/payment-logs?viewer_id={TEST_TEACHER_ID}')

    print(f"\n=== GET /payment-logs? Teacher ID RESPONSE ===")
    print(f"Status Code: {response.status_code}")
    print(f"Got {len(response.get_json())} logs for teacher user\nExamples:\n")
    response_data = response.get_json()
    pprint(response_data)
    print("===================================\n")

    assert response.status_code == 200
    assert isinstance(response.get_json(), list)

def test_post_payment_log(client):

    # 1. Arrange: Prepare the test data
    frontend_post_content = {
            'teacher_id': 'dcef54de-bc89-4388-a7a8-dba5d8327447',
            'parent_id': 'a6934e55-9538-4c06-a7b0-545fbd4d8cee',
            'amount_paid': 36,
            'notes': '',
            'payment_date': '2025-10-11T00:00:00.000Z'}

    # 2. Act: Send the POST request
    response = client.post('/payment-logs', json=frontend_post_content)

    # 3. Assert: Verify the response and the database state
    assert response.status_code == 201  # 201 Created is the standard for successful POSTs

    response_data = response.get_json()
    pprint(response_data)


