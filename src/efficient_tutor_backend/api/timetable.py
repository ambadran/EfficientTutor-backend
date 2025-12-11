'''
API endpoints for viewing the generated Timetable.
'''
from typing import Annotated, Any, Union
from fastapi import APIRouter, Depends

from ..database import models as db_models
from ..models import timetable as timetable_models
from ..services.security import verify_token_and_get_user
from ..services.timetable_service import TimeTableService


class TimetableAPI:
    """
    A class to encapsulate endpoints for the Timetable.
    """
    def __init__(self):
        self.router = APIRouter(
            prefix="/timetable",
            tags=["Timetable"]
        )
        self._register_routes()

    def _register_routes(self):
        """Registers all the API routes for this class."""
        self.router.add_api_route(
            "/", 
            self.get_timetable,
            methods=["GET"],
            response_model=list[timetable_models.TimeTableSlot])

    async def get_timetable(
        self,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        timetable_service: Annotated[TimeTableService, Depends(TimeTableService)]
    ) -> list[Any]:
        """
        Retrieves the generated timetable for the current user.
        - For a Teacher, returns their full schedule.
        - For a Parent, returns the schedules for all their children.
        - For a Student, returns their personal schedule.
        """
        return await timetable_service.get_timetable_for_api(current_user)

# Instantiate the class and export its router
timetable_api = TimetableAPI()
router = timetable_api.router
