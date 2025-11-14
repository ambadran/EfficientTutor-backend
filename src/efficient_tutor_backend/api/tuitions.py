'''
API endpoints for CRUD operations on Tuition Templates and their sub-resources.
'''
from typing import Annotated, Any, List, Union
from uuid import UUID
from fastapi import APIRouter, Depends, Response, status, HTTPException

from ..database import models as db_models
from ..database.db_enums import UserRole
from ..models import tuition as tuition_models
from ..models import meeting_links as meeting_link_models
from ..services.security import verify_token_and_get_user
from ..services.tuition_service import TuitionService

# Define a union type for role-based responses
TuitionReadRoleBased = Union[
    tuition_models.TuitionReadForTeacher,
    tuition_models.TuitionReadForParent,
    tuition_models.TuitionReadForStudent,
]


class TuitionsAPI:
    """
    A class to encapsulate CRUD endpoints for Tuition Templates.
    """
    def __init__(self):
        self.router = APIRouter(
            prefix="/tuitions",
            tags=["Tuitions"]
        )
        self._register_routes()

    def _register_routes(self):
        """Registers all the API routes for this class."""
        # CRUD for Tuition Templates
        self.router.add_api_route(
                "/", 
                self.list_tuitions, 
                methods=["GET"], 
                response_model=List[TuitionReadRoleBased])
        self.router.add_api_route(
                "/regenerate", 
                self.regenerate_tuitions, 
                methods=["POST"], 
                status_code=status.HTTP_202_ACCEPTED)
        self.router.add_api_route(
                "/{tuition_id}", 
                self.get_tuition, 
                methods=["GET"], 
                response_model=TuitionReadRoleBased)
        self.router.add_api_route(
                "/{tuition_id}", 
                self.update_tuition, 
                methods=["PATCH"], 
                response_model=tuition_models.TuitionReadForTeacher)

        # CRUD for Meeting Link sub-resource
        self.router.add_api_route(
                "/{tuition_id}/meeting_link", 
                self.create_meeting_link, 
                methods=["POST"], 
                status_code=status.HTTP_201_CREATED, 
                response_model=meeting_link_models.MeetingLinkRead)
        self.router.add_api_route(
                "/{tuition_id}/meeting_link", 
                self.update_meeting_link, 
                methods=["PATCH"], 
                response_model=meeting_link_models.MeetingLinkRead)
        self.router.add_api_route(
                "/{tuition_id}/meeting_link", 
                self.delete_meeting_link, 
                methods=["DELETE"], 
                status_code=status.HTTP_204_NO_CONTENT)

    async def list_tuitions(
        self,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)]
    ) -> List[Any]:
        """
        Retrieves a list of all tuition templates visible to the current user.
        The response model varies based on the user's role.
        """
        # The service returns a list of dicts; FastAPI validates against the Union response_model
        return await tuition_service.get_all_tuitions_for_api(current_user)

    async def get_tuition(
        self,
        tuition_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)]
    ) -> Any:
        """
        Retrieves a single tuition template by its ID.
        The response model varies based on the user's role.
        """
        # The service returns a dict; FastAPI validates against the Union response_model
        return await tuition_service.get_tuition_by_id_for_api(tuition_id, current_user)

    async def update_tuition(
        self,
        tuition_id: UUID,
        update_data: tuition_models.TuitionUpdate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)]
    ) -> Any:
        """
        Updates a tuition template's details (e.g., duration, charges).
        Restricted to the owning teacher. Returns the updated tuition from the teacher's perspective.
        """
        return await tuition_service.update_tuition_by_id(tuition_id, update_data, current_user)

    async def create_meeting_link(
        self,
        tuition_id: UUID,
        link_data: meeting_link_models.MeetingLinkCreate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)]
    ):
        """
        Creates a meeting link for a tuition. Restricted to the owning teacher.
        """
        return await tuition_service.create_meeting_link_for_api(tuition_id, link_data, current_user)

    async def update_meeting_link(
        self,
        tuition_id: UUID,
        link_data: meeting_link_models.MeetingLinkUpdate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)]
    ):
        """
        Updates an existing meeting link for a tuition. Restricted to the owning teacher.
        """
        return await tuition_service.update_meeting_link_for_api(tuition_id, link_data, current_user)

    async def delete_meeting_link(
        self,
        tuition_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)]
    ):
        """
        Deletes a meeting link from a tuition. Restricted to the owning teacher.
        """
        await tuition_service.delete_meeting_link(tuition_id, current_user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def regenerate_tuitions(
        self,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)]
    ):
        """
        Triggers a full regeneration of all tuition templates.
        This is a powerful administrative action that rebuilds tuitions based on
        current student subject enrollments.
        **This endpoint is restricted to Admins only.**
        """
        # Authorization Check
        if current_user.role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This action is restricted to administrators."
            )
        
        success = await tuition_service.regenerate_all_tuitions()
        if success:
            return {"message": "Tuition regeneration process started successfully."}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Tuition regeneration failed.")


# Instantiate the class and export its router
tuitions_api = TuitionsAPI()
router = tuitions_api.router
