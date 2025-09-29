from dotenv import load_dotenv
import os
import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# This line loads BOTH DATABASE_URL and DATABASE_URL_TEST into the environment
load_dotenv()

# --- START: New Logic ---
# Get the test database URL from the environment
test_db_url = os.environ.get('DATABASE_URL_TEST')

# If the test URL exists, overwrite the main DATABASE_URL for this session
if test_db_url:
    os.environ['DATABASE_URL'] = test_db_url
    print("--- Running with LOCAL TEST DATABASE ---")
else:
    raise ValueError("test db environment variable not set")
# --- END: New Logic ---

# Now that the environment is set up, we can safely import the app factory
# It will now see the overwritten DATABASE_URL
from src.efficient_tutor_backend import create_app

if __name__ == '__main__':
    # Create the app instance using the factory
    app = create_app()
    
    # Run the app in debug mode
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port)

