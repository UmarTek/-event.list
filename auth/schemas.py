"""
Схемы для аутентификации
"""

from pydantic import BaseModel


class PhoneRequest(BaseModel):
    phone: str


class CodeVerification(BaseModel):
    phone: str
    code: str