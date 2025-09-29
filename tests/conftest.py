'''
all the fixtures are defined here
'''
import pytest
import os
from dotenv import load_dotenv
from efficient_tutor_backend.database.db_handler import DatabaseHandler
from efficient_tutor_backend import create_app

# Load environment variables once when pytest starts
load_dotenv()

@pytest.fixture
def db_handler(monkeypatch) -> DatabaseHandler:
    """
    Provides a DatabaseHandler instance that is guaranteed to use the
    test database URL, with proper setup and teardown.
    """
    # 1. Force-reset the singleton pool to ensure a fresh start
    if DatabaseHandler._pool:
        DatabaseHandler._pool.closeall()
    DatabaseHandler._pool = None

    # 2. Get the test database URL
    test_db_url = os.environ.get('DATABASE_URL_TEST')
    
    # 3. Add a safety check
    if not test_db_url:
        pytest.fail("DATABASE_URL_TEST is not set. Aborting tests.")

    # 4. Use monkeypatch to set the DATABASE_URL for this test
    monkeypatch.setenv('DATABASE_URL', test_db_url)
    
    # 5. Now, creating the instance is safe and will create a new pool
    handler = DatabaseHandler()
    yield handler
    
    # 6. Teardown: close all connections after the test is done
    if handler._pool:
        handler._pool.closeall()
    DatabaseHandler._pool = None

@pytest.fixture
def app(monkeypatch):
    """
    Create and configure a new app instance for each test, ensuring it
    connects to the test database.
    """
    # Force-reset the singleton pool
    if DatabaseHandler._pool:
        DatabaseHandler._pool.closeall()
    DatabaseHandler._pool = None

    # Get the test database URL and perform a safety check
    test_db_url = os.environ.get('DATABASE_URL_TEST')
    if not test_db_url:
        pytest.fail("DATABASE_URL_TEST is not set. Aborting tests.")

    # Use monkeypatch to set the correct DATABASE_URL for the app
    monkeypatch.setenv('DATABASE_URL', test_db_url)

    # Now, it's safe to create the app instance
    app = create_app()
    app.config['TESTING'] = True

    # --- THE FIX ---
    # Explicitly initialize the database pool within the app's context
    with app.app_context():
        DatabaseHandler()
    # ---------------

    yield app

    # Teardown: Clean up the database pool after the test
    if DatabaseHandler._pool:
        DatabaseHandler._pool.closeall()
    DatabaseHandler._pool = None

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

