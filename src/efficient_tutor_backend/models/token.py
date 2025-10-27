'''

'''
from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None

# Data from the JWT payload
class TokenPayload(BaseModel):
    # 'sub' is the JWT Subject claim, typically the user's unique identifier
    sub: EmailStr
    id: int # Optionally include user ID for quick lookup
