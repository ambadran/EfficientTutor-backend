'''
This file contains common security-related utilities, such as password hashing,
that are decoupled from other services to prevent circular imports.
'''
from passlib.context import CryptContext

# --- Password Hashing ---
class HashedPassword:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    @classmethod
    def verify(cls, plain_password: str, hashed_password: str) -> bool:
        return cls.pwd_context.verify(plain_password, hashed_password)

    @classmethod
    def get_hash(cls, password: str) -> str:
        return cls.pwd_context.hash(password)
