'''

'''
from datetime import timedelta
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .security import HashedPassword, JWTHandler
from ..database import models as db_models
from ..database.engine import get_db_session
from ..models import token as token_models
from ..common.logger import log

class LoginService:
    def __init__(self, db: Annotated[AsyncSession, Depends(get_db_session)]):
        self.db = db

    async def login_user(self, form_data: OAuth2PasswordRequestForm) -> token_models.Token:
        log.info(f"Attempting login for user: {form_data.username}")
        user = await self._get_user_by_email_with_password(form_data.username)

        if not user or not HashedPassword.verify(form_data.password, user.hashed_password):
            log.warning(f"Login failed for user: {form_data.username} - Incorrect email or password")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = JWTHandler.create_access_token(subject=user.email)
        log.info(f"Login successful for user: {form_data.username}")

        return token_models.Token(access_token=access_token, token_type="bearer")

    async def _get_user_by_email_with_password(self, email: str) -> db_models.Users | None:
        """Fetches user including the password hash (internal use only)."""
        result = await self.db.execute(
            select(db_models.Users).filter(db_models.Users.email == email)
        )
        return result.scalars().first()

    # --- NEW: Users lookup for dependency ---
    async def get_active_user_by_email(self, email: str) -> db_models.Users | None:
        """Fetches an active user by email."""
        result = await self.db.execute(
            select(db_models.Users).filter(db_models.Users.email == email, db_models.Users.is_active == True)
        )
        return result.scalars().first()
