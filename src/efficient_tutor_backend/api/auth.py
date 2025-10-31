'''

'''
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

# Import the service and use it via dependency injection
from ..services.auth_service import LoginService
from ..models import token as token_models
from ..common.logger import log

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

# /signup endpoint remains removed for now as per previous plan
# We will add it back when we implement UserService

@router.post("/login", response_model=token_models.Token)
async def login_for_access_token(
    # Use Annotated for dependencies
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    login_service: Annotated[LoginService, Depends(LoginService)] # Inject LoginService
):
    """
    Authenticates a user and returns an access token.
    Uses OAuth2PasswordRequestForm (username & password fields).
    """
    try:
        # Delegate directly to the service
        token = await login_service.login_user(form_data)
        return token
    except HTTPException as e:
        # Re-raise HTTPExceptions raised by the service
        raise e
    except Exception as e:
        # Catch unexpected errors
        log.error(f"Unexpected error during login: {e}", exc_info=True) # Logging should be in service
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred during login.",
        )
