'''
API endpoints for managing Notes.
'''
from typing import Annotated, Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, status, Response

from ..database import models as db_models
from ..models import notes as notes_models
from ..services.security import verify_token_and_get_user
from ..services.notes_service import NotesService

class NotesAPI:
    """
    A class to encapsulate CRUD endpoints for Notes.
    """
    def __init__(self):
        self.router = APIRouter(
            prefix="/notes",
            tags=["Notes"]
        )
        self._register_routes()

    def _register_routes(self):
        """Registers all the API routes for this class."""
        self.router.add_api_route(
                "/", 
                self.list_notes, 
                methods=["GET"], 
                response_model=List[notes_models.NoteRead])

        self.router.add_api_route(
                "/{note_id}", 
                self.get_note, 
                methods=["GET"], 
                response_model=notes_models.NoteRead)

        self.router.add_api_route(
                "/", 
                self.create_note, 
                methods=["POST"], 
                status_code=status.HTTP_201_CREATED, 
                response_model=notes_models.NoteRead)

        self.router.add_api_route(
                "/{note_id}", 
                self.update_note, 
                methods=["PATCH"], 
                response_model=notes_models.NoteRead)

        self.router.add_api_route(
                "/{note_id}", 
                self.delete_note, 
                methods=["DELETE"], 
                status_code=status.HTTP_204_NO_CONTENT)

    async def list_notes(
        self,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        notes_service: Annotated[NotesService, Depends(NotesService)]
    ) -> List[Any]:
        """
        Retrieves a list of all notes visible to the current user.
        """
        return await notes_service.get_all_notes_for_api(current_user)

    async def get_note(
        self,
        note_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        notes_service: Annotated[NotesService, Depends(NotesService)]
    ) -> Any:
        """
        Retrieves a single note by its ID.
        """
        return await notes_service.get_note_by_id_for_api(note_id, current_user)

    async def create_note(
        self,
        note_data: notes_models.NoteCreate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        notes_service: Annotated[NotesService, Depends(NotesService)]
    ) -> Any:
        """
        Creates a new note. Restricted to Teachers only.
        """
        return await notes_service.create_note_for_api(note_data, current_user)

    async def update_note(
        self,
        note_id: UUID,
        note_data: notes_models.NoteUpdate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        notes_service: Annotated[NotesService, Depends(NotesService)]
    ) -> Any:
        """
        Updates an existing note. Restricted to the owning Teacher.
        """
        return await notes_service.update_note_for_api(note_id, note_data, current_user)

    async def delete_note(
        self,
        note_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        notes_service: Annotated[NotesService, Depends(NotesService)]
    ):
        """
        Deletes a specific note. Restricted to the owning Teacher.
        """
        await notes_service.delete_note(note_id, current_user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

# Instantiate the class and export its router
notes_api = NotesAPI()
router = notes_api.router
