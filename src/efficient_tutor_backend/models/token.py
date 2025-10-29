'''

'''
from pydantic import BaseModel, EmailStr
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

# REMOVED from original location
# class TokenData(BaseModel):
#     email: str | None = None

# --- NEW: Add TokenPayload here ---
class TokenPayload(BaseModel):
    sub: EmailStr # 'sub' is standard JWT claim for subject (the user's email)
    exp: datetime
