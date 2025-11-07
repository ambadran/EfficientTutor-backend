'''

'''
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from ..common.config import settings
from ..models.token import TokenPayload
from ..common.logger import log
from ..database import models as db_models
from .user_service import UserService

# --- Password Hashing ---
class HashedPassword:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    @classmethod
    def verify(cls, plain_password: str, hashed_password: str) -> bool:
        return cls.pwd_context.verify(plain_password, hashed_password)

    @classmethod
    def get_hash(cls, password: str) -> str:
        return cls.pwd_context.hash(password)

# --- JWT Handling ---
class JWTHandler:
    @staticmethod
    def create_access_token(
        subject: str,
        # Add default value using settings
        expires_delta: Optional[timedelta] = None
    ) -> str:
        if expires_delta is None:
            expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        expire = datetime.now(timezone.utc) + expires_delta
        to_encode = {"sub": str(subject), "exp": expire}
        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> TokenPayload | None:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            token_data = TokenPayload(**payload)
            return token_data
        except (JWTError, ValueError) as e: # Catch Pydantic validation errors too
            log.warning(f"JWT decode/validation error: {e}") # Add logging
            return None

# --- JWT Verification Dependency Function ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def verify_token_and_get_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_service: Annotated[UserService, Depends(UserService)]
    ) -> db_models.Users:
    """
    REFACTORED: Dependency to verify JWT, fetch the full polymorphic
    user (Parent, Student, or Teacher) via the UserService.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = JWTHandler.decode_token(token)
    if not token_data or not token_data.sub:
        log.warning("JWT decode failed or invalid token structure.")
        raise credentials_exception

    user = await user_service.get_user_by_email(token_data.sub)
    
    if user is None:
        log.warning(f"User '{token_data.sub}' not found during token verification.")
        raise credentials_exception
    
    if not user.is_active:
        log.warning(f"User '{token_data.sub}' is not active.")
        raise credentials_exception

    log.info(f"JWT verified successfully for user: {user.email} (Role: {user.role})")
    # This now returns the full Parent, Student, or Teacher object
    return user
