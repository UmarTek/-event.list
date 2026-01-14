"""
API endpoints для аутентификации
"""

from fastapi import APIRouter, status, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.schemas import PhoneRequest, CodeVerification
from auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Аутентификация"])


# Выносим функцию из dependencies прямо сюда
async def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/send-code", status_code=status.HTTP_200_OK)
async def send_auth_code(
    phone_request: PhoneRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Отправка кода аутентификации на телефон"""
    return await auth_service.send_code(phone_request.phone)


@router.post("/verify-code", status_code=status.HTTP_200_OK)
async def verify_auth_code(
    verification: CodeVerification,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Верификация кода и получение токена"""
    return await auth_service.verify_code(verification.phone, verification.code)


# Явно экспортируем router для импорта
__all__ = ['router']