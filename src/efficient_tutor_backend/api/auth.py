'''
API endpoints for Authentication including login and user creation (signup).
'''
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm

from ..services.auth_service import LoginService
from ..services.user_service import ParentService, TeacherService
from ..models import token as token_models
from ..models import user as user_models
from ..common.logger import log

class AuthRoutes:
    """
    A class to encapsulate all authentication and user creation endpoints.
    """
    def __init__(self):
        self.router = APIRouter(
            prefix="/auth",
            tags=["Authentication"]
        )
        self._register_routes()

    def _register_routes(self):
        """Registers all the API routes for this class."""
        self.router.add_api_route(
            "/login",
            self.login_for_access_token,
            methods=["POST"],
            response_model=token_models.Token,
            summary="Login for Access Token"
        )
        self.router.add_api_route(
            "/signup/parent",
            self.signup_parent,
            methods=["POST"],
            response_model=user_models.ParentRead,
            status_code=status.HTTP_201_CREATED,
            summary="Parent Signup"
        )
        self.router.add_api_route(
            "/signup/teacher",
            self.signup_teacher,
            methods=["POST"],
            response_model=user_models.TeacherRead,
            status_code=status.HTTP_201_CREATED,
            summary="Teacher Signup"
        )

    async def login_for_access_token(
        self,
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        login_service: Annotated[LoginService, Depends(LoginService)]
    ):
        """
        Authenticates a user and returns an access token.
        Uses OAuth2PasswordRequestForm (username & password fields).
        """
        try:
            token = await login_service.login_user(form_data)
            return token
        except HTTPException as e:
            raise e
        except Exception as e:
            log.error(f"Unexpected error during login: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An internal server error occurred during login.",
            )

    async def signup_parent(
        self,
        parent_data: user_models.ParentCreate,
        request: Request,
        parent_service: Annotated[ParentService, Depends(ParentService)]
    ):
        """
        Handles the creation of a new parent user.
        Timezone and currency are determined automatically from the request IP.
        """
        client_ip = request.client.host
        new_parent = await parent_service.create_parent(parent_data, ip_address=client_ip)
        return new_parent

    async def signup_teacher(
        self,
        teacher_data: user_models.TeacherCreate,
        request: Request,
        teacher_service: Annotated[TeacherService, Depends(TeacherService)]
    ):
        """
        Handles the creation of a new teacher user.
        Timezone and currency are determined automatically from the request IP.
        """
        client_ip = request.client.host
        new_teacher = await teacher_service.create_teacher(teacher_data, ip_address=client_ip)
        return new_teacher

# Create an instance of the class and export its router
auth_routes = AuthRoutes()
router = auth_routes.router
