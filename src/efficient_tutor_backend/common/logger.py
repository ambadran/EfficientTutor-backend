'''
universal logger
'''
# In src/efficient_tutor_backend/common/logger.py
import logging
import sys

def setup_logger():
    """
    Configures and returns a root logger for the application.
    """
    logger = logging.getLogger('ET-backend')
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    
    # This adds the module name and pads it to 18 characters for clean alignment.
    formatter = logging.Formatter(
        '%(asctime)s - %(module)s - %(levelname)s\n - %(message)s'
    )
    handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(handler)

    return logger

# Create a single logger instance to be imported by other modules
log = setup_logger()
