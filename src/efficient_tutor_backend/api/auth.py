from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.engine import get_db_session
from ..services.auth_service import AuthService
from ..models import user as user_models
from ..models import token as token_models
from ..common.config import settings

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)
auth_service = AuthService()

@router.post("/signup", response_model=user_models.UserRead, status_code=status.HTTP_201_CREATED)
async def signup(
    user: user_models.UserCreate,
    db: AsyncSession = Depends(get_db_session)
):
    db_user = await auth_service.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return await auth_service.create_user(db=db, user=user)

@router.post("/login", response_model=token_models.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session)
):
    user = await auth_service.get_user_by_email(db, email=form_data.username)
    if not user or not auth_service.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
