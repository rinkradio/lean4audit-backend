import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator

from app.models.user import UserRole


class LoginRequest(BaseModel):
    employee_id: str
    password: str

    @field_validator("employee_id")
    @classmethod
    def strip_employee_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Employee ID is required.")
        return v

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if not v:
            raise ValueError("Password is required.")
        return v


class UserOut(BaseModel):
    id: uuid.UUID
    employee_id: str
    full_name: str
    role: UserRole
    last_login: datetime | None = None

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
