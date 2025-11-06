'''

'''
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ..database.db_enums import MeetingLinkTypeEnum


class MeetingLinkBase(BaseModel):
    """
    Base Pydantic model with common fields for a Meeting Link.
    """
    meeting_link_type: MeetingLinkTypeEnum
    meeting_link: HttpUrl
    meeting_id: Optional[str] = None
    meeting_password: Optional[str] = None


class MeetingLinkCreate(MeetingLinkBase):
    """
    Pydantic model for validating the JSON payload when CREATING a new link.
    'tuition_id' is NOT included here because it will be provided
    via the URL path (e.g., /tuitions/{tuition_id}/meeting_link).
    """
    pass # Inherits all fields from MeetingLinkBase


class MeetingLinkUpdate(BaseModel):
    """
    Pydantic model for validating the JSON payload when UPDATING a link.
    All fields are optional for partial PATCH updates.
    """
    meeting_link_type: Optional[MeetingLinkTypeEnum] = None
    meeting_link: Optional[HttpUrl] = None
    meeting_id: Optional[str] = None
    meeting_password: Optional[str] = None


class MeetingLinkRead(MeetingLinkBase):
    """
    Pydantic model for formatting a link when READING it from the API.
    This is what will be nested inside the TuitionRead... models.
    """
    tuition_id: UUID

    # This allows the model to be created directly from the
    # db_models.MeetingLinks ORM object.
    model_config = ConfigDict(from_attributes=True)
