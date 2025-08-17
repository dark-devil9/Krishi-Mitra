# schemas.py
from pydantic import BaseModel
from typing import Optional

# Defines the shape of the data when creating a user
class UserCreate(BaseModel):
    phone_number: str
    name: str
    pincode: str
    age: Optional[int] = None
    gender: Optional[str] = None
    income: Optional[float] = None

# Defines the shape of the data when reading a user from the DB
class User(UserCreate):
    id: int

    class Config:
        from_attributes = True # Pydantic V2 uses this instead of orm_mode