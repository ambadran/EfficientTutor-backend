'''

'''
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from ..common.config import settings
from ..database import models as db_models
from ..database.engine import get_db_session # Need this dependency later
from ..database import models as db_models
from ..models import user as user_models

# This defines how FastAPI extracts the token (from 'Authorization: Bearer <token>')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login") # Point to your login endpoint

# Setup password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[db_models.User]:
        result = await db.execute(select(db_models.User).filter(db_models.User.email == email))
        return result.scalars().first()

    async def create_user(self, db: AsyncSession, user: user_models.UserCreate) -> db_models.User:
        db_user = db_models.User(
            email=user.email,
            hashed_password=self.get_password_hash(user.password),
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        # TODO: Add logic to also create a parent/teacher/student profile entry
        return db_user

    async def get_current_user(
        self,
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db_session)
    ) -> db_models.User:
        """
        Dependency function to get the current authenticated user from the token.
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
            token_data = token_models.TokenData(email=email)
        except JWTError:
            raise credentials_exception

        user = await self.get_user_by_email(db, email=token_data.email)
        if user is None:
            raise credentials_exception
        return user

# Instantiate the service to be used by the dependency function
auth_service_instance = AuthService()
# Create the actual dependency function that FastAPI will use
async def get_current_active_user(
    current_user: db_models.User = Depends(auth_service_instance.get_current_user)
) -> db_models.User:
    # You could add checks here later, e.g., if the user is active/verified
    # if not current_user.is_active:
    #     raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
