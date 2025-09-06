from dotenv import load_dotenv
import os
import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# This line is crucial: it loads the variables from your .env file
# into the environment, making them available to your application.
load_dotenv()

# Now that the environment is set up, we can safely import the app factory
from src.efficient_tutor_backend import create_app

if __name__ == '__main__':
    # Create the app instance using the factory
    app = create_app()
    
    # Run the app in debug mode. Debug mode provides helpful error messages
    # and automatically reloads the server when you save a file.
    # The port can be any available port, 5000 is a common choice for Flask.
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port)
