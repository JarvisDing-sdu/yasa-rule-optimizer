"""Auth request/response schemas."""
from pydantic import BaseModel, EmailStr

class SendCodeRequest(BaseModel):
    email: EmailStr

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    code: str

class LoginRequest(BaseModel):
    email: str  # 接受任意字符串作为账号名，不强制邮箱格式
    password: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str
