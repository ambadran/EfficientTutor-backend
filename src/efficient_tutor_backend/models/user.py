'''

'''
import uuid
from pydantic import BaseModel, EmailStr
from ..database.models import UserRole # Import the enum

# Pydantic model for data received when creating a user
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: UserRole

# Pydantic model for data returned from the API
class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole

    class Config:
        from_attributes = True # Formerly orm_mode = True
