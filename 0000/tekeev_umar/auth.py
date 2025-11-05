"""
Модуль аутентификации через отправку кода с интеграцией msg.ovrx.ru
"""

import random
import string
import uuid
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends, Header
from sqlalchemy.orm import Session
from database import get_db, User, AuthCode
import phonenumbers
from typing import Optional

# Импортируем SMS сервис
from sms_service import sms_service


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def generate_code(self, length: int = 6) -> str:
        """Генерация 6-значного цифрового кода"""
        return ''.join(random.choices(string.digits, k=length))

    def validate_phone_number(self, phone: str) -> Optional[str]:
        """Валидация номера телефона"""
        try:
            parsed_phone = phonenumbers.parse(phone, "RU")
            if phonenumbers.is_valid_number(parsed_phone):
                return phonenumbers.format_number(
                    parsed_phone,
                    phonenumbers.PhoneNumberFormat.E164
                )
        except phonenumbers.NumberParseException:
            pass

        # Дополнительная проверка для российских номеров
        cleaned = ''.join(c for c in phone if c.isdigit())
        if cleaned.startswith('7') and len(cleaned) == 11:
            return '+' + cleaned
        elif cleaned.startswith('8') and len(cleaned) == 11:
            return '+7' + cleaned[1:]

        return None

    async def send_code(self, phone: str) -> dict:
        """
        Отправка кода аутентификации через msg.ovrx.ru/auth-code/sms
        """

        # Валидируем номер телефона
        normalized_phone = self.validate_phone_number(phone)
        if not normalized_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат номера телефона. Используйте российский номер: +79123456789 или 89123456789"
            )

        # Ищем существующего пользователя или создаем нового
        user = self.db.query(User).filter(User.phone == normalized_phone).first()
        if not user:
            user = User(
                user_id=str(uuid.uuid4()),
                phone=normalized_phone,
                name=f"User_{normalized_phone}",
                is_verified=False
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

        # Генерируем код
        code = self.generate_code()
        expires_at = datetime.now() + timedelta(minutes=10)

        # Сохраняем код в базу
        auth_code = AuthCode(
            user_id=user.user_id,
            code=code,
            expires_at=expires_at
        )
        self.db.add(auth_code)
        self.db.commit()

        # Отправляем код через msg.ovrx.ru
        print(f"🔄 Отправка кода {code} на номер {normalized_phone} через msg.ovrx.ru")
        sms_result = await sms_service.send_auth_code(normalized_phone, code)

        # Формируем ответ в зависимости от результата отправки
        if sms_result.get("status_code") == 201:
            return {
                "message": "Код авторизации отправлен на ваш телефон через msg.ovrx.ru",
                "expires_in": "10 минут",
                "service_response": sms_result.get("data", {}),
                "status": "success",
                "sms_service": "msg.ovrx.ru"
            }
        else:
            # Если не удалось отправить через сервис
            error_msg = sms_result.get('error', 'Неизвестная ошибка')
            print(f"⚠️ Ошибка отправки через msg.ovrx.ru: {error_msg}")

            # В демо-режиме возвращаем код в ответе
            return {
                "message": "Сервис отправки SMS временно недоступен. Используйте код для тестирования:",
                "code": code,  # Только для разработки!
                "expires_in": "10 минут",
                "service_error": error_msg,
                "sms_service": "fallback",
                "status": "fallback"
            }

    async def verify_code(self, phone: str, code: str) -> dict:
        """Верификация кода и аутентификация пользователя"""

        normalized_phone = self.validate_phone_number(phone)
        if not normalized_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат номера телефона"
            )

        # Ищем пользователя
        user = self.db.query(User).filter(User.phone == normalized_phone).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )

        # Ищем активный код
        auth_code = self.db.query(AuthCode).filter(
            AuthCode.user_id == user.user_id,
            AuthCode.code == code,
            AuthCode.expires_at > datetime.now(),
            AuthCode.is_used == False
        ).first()

        if not auth_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный или просроченный код"
            )

        # Помечаем код как использованный
        auth_code.is_used = True

        # Активируем пользователя
        if not user.is_verified:
            user.is_verified = True

        self.db.commit()

        # Генерируем токен
        token = self._generate_token(user.user_id)

        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": user.user_id,
            "is_verified": user.is_verified,
            "message": "Успешная авторизация через msg.ovrx.ru"
        }

    def _generate_token(self, user_id: str) -> str:
        """Генерация токена"""
        return f"eventlist_token_{user_id}_{datetime.now().timestamp()}"


# Зависимости для FastAPI
async def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def get_current_user(
        authorization: str = Header(default="Bearer "),
        auth_service: AuthService = Depends(get_auth_service),
        db: Session = Depends(get_db)
) -> User:
    """Зависимость для получения текущего пользователя"""

    if not authorization or not authorization.startswith("Bearer "):
        # Демо-режим для тестирования
        user = db.query(User).first()
        if not user:
            user = User(
                user_id=str(uuid.uuid4()),
                phone="+79000000000",
                name="Demo_User",
                is_verified=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    token = authorization.replace("Bearer ", "")

    try:
        if token.startswith("eventlist_token_"):
            parts = token.split('_')
            if len(parts) >= 3:
                user_id = parts[2]
                user = db.query(User).filter(User.user_id == user_id).first()
                if user:
                    return user

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный токен"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный токен"
        )