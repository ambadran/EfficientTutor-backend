"""
This file contains custom, application-specific exceptions.
"""

class UserNotFoundError(Exception):
    """Raised when a user ID is not found in the database."""
    pass

class UnauthorizedRoleError(Exception):
    """Raised when a user's role does not permit them to perform an action."""
    pass
