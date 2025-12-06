'''
API endpoints for managing Tuition Logs.
'''
from typing import Annotated, Any, Union
from uuid import UUID
from fastapi import APIRouter, Depends, status, Query

from ..database import models as db_models
from ..models import finance as finance_models
from ..services.security import verify_token_and_get_user
from ..services.finance_service import TuitionLogService

class TuitionLogsAPI:
    """
    A class to encapsulate endpoints for Tuition Logs.
    """
    def __init__(self):
        self.router = APIRouter(
            prefix="/tuition-logs",
            tags=["Tuition Logs"]
        )
        self._register_routes()

    def _register_routes(self):
        """Registers all the API routes for this class."""
        self.router.add_api_route(
            "/", 
            self.list_tuition_logs, 
            methods=["GET"], 
            response_model=list[finance_models.TuitionLogReadRoleBased])
        self.router.add_api_route(
            "/{log_id}", 
            self.get_tuition_log, 
            methods=["GET"], 
            response_model=finance_models.TuitionLogReadRoleBased)
        self.router.add_api_route(
            "/", 
            self.create_tuition_log, 
            methods=["POST"], 
            status_code=status.HTTP_201_CREATED, 
            response_model=finance_models.TuitionLogReadForTeacher)
        self.router.add_api_route(
            "/{log_id}/void", 
            self.void_tuition_log, 
            methods=["PATCH"])

        self.router.add_api_route(
            "/{log_id}/correction", 
            self.correct_tuition_log, 
            methods=["POST"], 
            response_model=finance_models.TuitionLogReadForTeacher)

    async def list_tuition_logs(
        self,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        tuition_log_service: Annotated[TuitionLogService, Depends(TuitionLogService)],
        student_id: Annotated[UUID | None, Query(description="Optional filter for Student ID")] = None,
        parent_id: Annotated[UUID | None, Query(description="Optional filter for Parent ID")] = None,
        teacher_id: Annotated[UUID | None, Query(description="Optional filter for Teacher ID")] = None
    ) -> list[Any]:
        """
        Retrieves a list of all tuition logs relevant to the current user.
        The response model varies based on the user's role.
        """
        return await tuition_log_service.get_all_tuition_logs_for_api(
            current_user,
            student_id=student_id,
            parent_id=parent_id,
            teacher_id=teacher_id
        )

    async def get_tuition_log(
        self,
        log_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        tuition_log_service: Annotated[TuitionLogService, Depends(TuitionLogService)]
    ) -> Any:
        """
        Retrieves a single tuition log by its ID.
        The response model varies based on the user's role.
        """
        return await tuition_log_service.get_tuition_log_by_id_for_api(log_id, current_user)

    async def create_tuition_log(
        self,
        log_data: finance_models.TuitionLogCreateHint,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        tuition_log_service: Annotated[TuitionLogService, Depends(TuitionLogService)]
    ) -> Any:
        """
        Creates a new tuition log. Restricted to Teachers only.
        """
        return await tuition_log_service.create_tuition_log(log_data.model_dump(), current_user)

    async def void_tuition_log(
        self,
        log_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        tuition_log_service: Annotated[TuitionLogService, Depends(TuitionLogService)]
    ):
        """
        Voids a specific tuition log. Restricted to the owning Teacher.
        """
        await tuition_log_service.void_tuition_log(log_id, current_user)
        return {"message": "Tuition log voided successfully."}

    async def correct_tuition_log(
        self,
        log_id: UUID,
        correction_data: finance_models.TuitionLogCreateHint,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        tuition_log_service: Annotated[TuitionLogService, Depends(TuitionLogService)]
    ) -> Any:
        """
        Corrects a tuition log by voiding the old one and creating a new one.
        Restricted to the owning Teacher.
        """
        return await tuition_log_service.correct_tuition_log(log_id, correction_data.model_dump(), current_user)


# Instantiate the class and export its router
tuition_logs_api = TuitionLogsAPI()
router = tuition_logs_api.router
