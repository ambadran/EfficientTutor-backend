import pytest
from src.efficient_tutor_backend import create_app

@pytest.fixture()
def app():
    """Create and configure a new app instance for each test."""
    # The create_app factory from your __init__.py is used here
    app = create_app()
    app.config.update({
        "TESTING": True,
    })
    yield app

@pytest.fixture()
def client(app):
    """A test client for the app."""
    return app.test_client()

def test_health_check(client):
    """
    Test the health check endpoint to ensure the server is responsive.
    """
    response = client.get('/')
    assert response.status_code == 200
    json_data = response.get_json()
    assert "status" in json_data
    assert json_data["status"] == "ok"
