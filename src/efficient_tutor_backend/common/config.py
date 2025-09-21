'''
Holds all the configurations
'''
import os
from dotenv import load_dotenv

load_dotenv()

# The timezone for all application-level date/time conversions and displays.
# Using the IANA Time Zone Database name is the best practice.
APP_TIMEZONE = os.environ.get('APP_TIMEZONE', 'Africa/Cairo')
