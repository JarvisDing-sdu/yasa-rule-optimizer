"""Auth request/response schemas."""
from pydantic import BaseModel, EmailStr

class SendCodeRequest(BaseModel):
    email: EmailStr

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    code: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str
