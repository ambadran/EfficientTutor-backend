from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

# Import the blueprint containing all the web routes
from .backend.app import main_routes

def create_app():
    """
    The application factory for the EfficientTutor Backend service.
    
    Its sole responsibility is to create and configure the Flask app
    that serves the parent/student frontend.
    """
    # Load environment variables from a .env file for local development
    load_dotenv()
    
    app = Flask(__name__)
    
    # Enable Cross-Origin Resource Sharing for the frontend to be able to
    # make requests to this backend.
    CORS(app)
    
    # Register all the API endpoints (like /login, /students, etc.)
    # that are defined in the backend/app.py file.
    app.register_blueprint(main_routes)

    # Note: The CSP background worker thread is INTENTIONALLY REMOVED.
    # That logic now lives in its own dedicated repository and service.
    
    return app
