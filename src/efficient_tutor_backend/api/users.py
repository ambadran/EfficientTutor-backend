'''

'''
from typing import Annotated
from fastapi import APIRouter, Depends

from ..database import models as db_models
from ..models import user as user_models
# Import the actual dependency function
from ..services.security import verify_token_and_get_user

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.get("/me", response_model=user_models.UserRead)
async def read_users_me(
    # Use the correct dependency function
    current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)]
):
    """
    Returns the profile information for the currently authenticated user.
    Requires a valid Bearer token in the Authorization header.
    """
    return current_user
