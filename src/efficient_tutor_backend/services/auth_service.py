'''

'''
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from .security import HashedPassword, JWTHandler
from .user_service import UserService  # CHANGED: Import UserService
from ..database import models as db_models
from ..models import token as token_models
from ..common.logger import log

class LoginService:
    """
    Service for handling user login and authentication.
    Depends on the UserService to fetch user data.
    """
    def __init__(
        self, 
        user_service: Annotated[UserService, Depends(UserService)]
    ):
        self.user_service = user_service

    async def login_user(self, form_data: OAuth2PasswordRequestForm) -> token_models.Token:
        log.info(f"Attempting login for user: {form_data.username}")
        
        # CHANGED: Call the UserService to fetch the user
        user = await self.user_service._get_user_by_email_with_password(form_data.username)

        if not user or not HashedPassword.verify(form_data.password, user.password):
            log.warning(f"Login failed for user: {form_data.username} - Incorrect email or password")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.is_active:
            log.warning(f"Login failed for user: {form_data.username} - User is inactive.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user."
            )

        access_token = JWTHandler.create_access_token(subject=user.email)
        log.info(f"Login successful for user: {form_data.username}")

        return token_models.Token(access_token=access_token, token_type="bearer")
