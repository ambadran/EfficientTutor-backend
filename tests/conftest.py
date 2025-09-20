'''
all the fixtures are defined here
'''
import pytest
from efficient_tutor_backend.database.db_handler import DatabaseHandler
from efficient_tutor_backend import create_app

@pytest.fixture
def db_handler() -> DatabaseHandler:
    """Provides a fresh DatabaseHandler instance for each test."""
    return DatabaseHandler()

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    app.config['TESTING'] = True
    
    with app.app_context():
        # Set up any test data if needed
        yield app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()
