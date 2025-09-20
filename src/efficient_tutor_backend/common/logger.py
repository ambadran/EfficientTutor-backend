'''
universal logger
'''
# src/efficient_tutor_backend/common/logger.py
import logging
import sys

def setup_logger():
    """
    Configures and returns a root logger for the application.
    """
    # Create a logger
    logger = logging.getLogger('ET-backend')
    logger.setLevel(logging.INFO) # Set the lowest level of message to handle

    # Create a handler to write messages to the console (stdout)
    handler = logging.StreamHandler(sys.stdout)
    
    # Create a formatter to define the log message format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)

    # Add the handler to the logger
    # This check prevents adding duplicate handlers if the function is called more than once
    if not logger.handlers:
        logger.addHandler(handler)

    return logger

# Create a single logger instance to be imported by other modules
log = setup_logger()
