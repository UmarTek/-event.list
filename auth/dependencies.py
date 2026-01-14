"""
Зависимости FastAPI для аутентификации
"""

from fastapi import HTTPException, status, Depends, Header
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db, User


async def get_current_user(
    authorization: str = Header(..., description="Bearer токен"),
    db: Session = Depends(get_db)
) -> User:
    """Зависимость для получения текущего пользователя"""

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный формат токена. Используйте 'Bearer <токен>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.replace("Bearer ", "").strip()

    # Проверка токена
    if not token.startswith("eventlist_token_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        parts = token.split('_')
        if len(parts) >= 3:
            user_id = parts[2]
            user = db.query(User).filter(User.user_id == user_id).first()
            if user:
                # Проверяем не забанен ли пользователь
                if user.is_banned:
                    if user.banned_until and user.banned_until > datetime.now():
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Пользователь забанен до {user.banned_until}. Причина: {user.ban_reason}"
                        )
                    elif not user.banned_until:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Пользователь забанен навсегда. Причина: {user.ban_reason}"
                        )
                return user

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка проверки токена",
            headers={"WWW-Authenticate": "Bearer"},
        )