from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import models as db_models
from ..models import user as user_models
from ..services.auth_service import get_current_active_user # Import the dependency

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.get("/me", response_model=user_models.UserRead)
async def read_users_me(
    current_user: db_models.User = Depends(get_current_active_user)
):
    """
    Returns the profile information for the currently authenticated user.
    """
    return current_user
