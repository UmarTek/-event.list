"""
Основной модуль FastAPI приложения EventList
"""

from fastapi import FastAPI, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

# Импорты из наших модулей
from database import (
    get_db, User, Group, GroupMember, Event, EventRegistration,
    init_database
)
from auth import get_auth_service, AuthService, get_current_user
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Инициализация базы данных при старте
init_database()

app = FastAPI(
    title="EventList API",
    description="API для управления группами и событиями с аутентификацией по коду",
    version="2.0.0"
)


# =============================================================================
# PYDANTIC МОДЕЛИ
# =============================================================================

class PhoneRequest(BaseModel):
    phone: str


class CodeVerification(BaseModel):
    phone: str
    code: str


class UserUpdate(BaseModel):
    name: str
    email: Optional[EmailStr] = None


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    event_type: str
    date_time: datetime
    location: Optional[str] = None
    max_participants: Optional[int] = None


class ReminderSettings(BaseModel):
    remind_24h: bool = True
    remind_2h: bool = True
    remind_day: bool = True


class UserResponse(BaseModel):
    user_id: str
    phone: str
    email: Optional[str]
    name: str
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class GroupResponse(BaseModel):
    group_id: str
    name: str
    description: Optional[str]
    created_by: str
    created_at: datetime
    member_count: int


class EventResponse(BaseModel):
    event_id: str
    title: str
    description: Optional[str]
    event_type: str
    date_time: datetime
    location: Optional[str]
    max_participants: Optional[int]
    current_participants: int
    created_by: str
    group_id: str
    created_at: datetime


class RegistrationResponse(BaseModel):
    success: bool
    message: str
    registration_type: str
    event_id: str


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def is_group_admin(db: Session, group_id: str, user_id: str) -> bool:
    """Проверка, является ли пользователь администратором группы"""
    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    ).first()
    return membership and membership.role == 'admin'


def is_group_member(db: Session, group_id: str, user_id: str) -> bool:
    """Проверка, является ли пользователь участником группы"""
    return db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    ).first() is not None


def get_event_participants_count(db: Session, event_id: str) -> int:
    """Получение количества участников события"""
    return db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.registration_type == 'confirmed'
    ).count()


# =============================================================================
# ЭНДПОИНТЫ АУТЕНТИФИКАЦИИ
# =============================================================================

@app.post("/auth/send-code", status_code=status.HTTP_200_OK)
async def send_auth_code(
        phone_request: PhoneRequest,
        auth_service: AuthService = Depends(get_auth_service)
):
    """Отправка кода аутентификации на телефон"""
    return await auth_service.send_code(phone_request.phone)


@app.post("/auth/verify-code", status_code=status.HTTP_200_OK)
async def verify_auth_code(
        verification: CodeVerification,
        auth_service: AuthService = Depends(get_auth_service)
):
    """Верификация кода и получение токена"""
    return await auth_service.verify_code(verification.phone, verification.code)


# =============================================================================
# ЭНДПОИНТЫ ПОЛЬЗОВАТЕЛЕЙ
# =============================================================================

@app.get("/users/me", response_model=UserResponse)
async def get_current_user_endpoint(
        current_user: User = Depends(get_current_user)
):
    """Получение информации о текущем пользователе"""
    return current_user


@app.put("/users/me", response_model=UserResponse)
async def update_current_user(
        user_data: UserUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Обновление данных текущего пользователя"""
    user = db.query(User).filter(User.user_id == current_user.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    user.name = user_data.name
    if user_data.email:
        user.email = user_data.email

    db.commit()
    db.refresh(user)
    return user


# =============================================================================
# ЭНДПОИНТЫ ГРУПП
# =============================================================================

@app.post("/groups/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
        group_data: GroupCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Создание новой группы"""
    group_id = str(uuid.uuid4())
    new_group = Group(
        group_id=group_id,
        name=group_data.name,
        description=group_data.description,
        created_by=current_user.user_id
    )

    db.add(new_group)

    # Добавляем создателя как администратора
    admin_membership = GroupMember(
        group_id=group_id,
        user_id=current_user.user_id,
        role='admin'
    )
    db.add(admin_membership)

    db.commit()
    db.refresh(new_group)

    return GroupResponse(
        group_id=group_id,
        name=new_group.name,
        description=new_group.description,
        created_by=new_group.created_by,
        created_at=new_group.created_at,
        member_count=1
    )


@app.get("/groups/{group_id}", response_model=GroupResponse)
async def get_group(
        group_id: str,
        db: Session = Depends(get_db)
):
    """Получение информации о группе"""
    group = db.query(Group).filter(Group.group_id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )

    member_count = db.query(GroupMember).filter(GroupMember.group_id == group_id).count()

    return GroupResponse(
        group_id=group.group_id,
        name=group.name,
        description=group.description,
        created_by=group.created_by,
        created_at=group.created_at,
        member_count=member_count
    )


@app.get("/groups/", response_model=List[GroupResponse])
async def get_all_groups(db: Session = Depends(get_db)):
    """Получение списка всех групп"""
    groups = db.query(Group).all()
    result = []
    for group in groups:
        member_count = db.query(GroupMember).filter(GroupMember.group_id == group.group_id).count()
        result.append(GroupResponse(
            group_id=group.group_id,
            name=group.name,
            description=group.description,
            created_by=group.created_by,
            created_at=group.created_at,
            member_count=member_count
        ))
    return result


@app.post("/groups/{group_id}/join")
async def join_group(
        group_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Вступление пользователя в группу"""
    group = db.query(Group).filter(Group.group_id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )

    # Проверяем, не является ли пользователь уже участником
    if is_group_member(db, group_id, current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже являетесь участником этой группы"
        )

    # Добавляем пользователя в группу как участника
    new_member = GroupMember(
        group_id=group_id,
        user_id=current_user.user_id,
        role='member'
    )
    db.add(new_member)
    db.commit()

    return {"message": "Вы успешно вступили в группу"}


# =============================================================================
# ЭНДПОИНТЫ СОБЫТИЙ
# =============================================================================

@app.post("/groups/{group_id}/events/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
        group_id: str,
        event_data: EventCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Создание нового события в группе"""

    # Проверяем существование группы
    group = db.query(Group).filter(Group.group_id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )

    # Проверяем права доступа
    if not is_group_admin(db, group_id, current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администраторы группы могут создавать события"
        )

    # Валидация данных события
    if event_data.event_type == 'limited_seats' and not event_data.max_participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для событий с ограниченным количеством мест необходимо указать max_participants"
        )

    if event_data.event_type == 'unlimited' and event_data.max_participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для событий с неограниченным количеством мест не нужно указывать max_participants"
        )

    # Проверяем, что дата события в будущем
    if event_data.date_time <= datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата события должна быть в будущем"
        )

    # Создаем событие
    event_id = str(uuid.uuid4())
    new_event = Event(
        event_id=event_id,
        title=event_data.title,
        description=event_data.description,
        event_type=event_data.event_type,
        date_time=event_data.date_time,
        location=event_data.location,
        max_participants=event_data.max_participants,
        created_by=current_user.user_id,
        group_id=group_id
    )

    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    return EventResponse(
        event_id=event_id,
        title=new_event.title,
        description=new_event.description,
        event_type=new_event.event_type,
        date_time=new_event.date_time,
        location=new_event.location,
        max_participants=new_event.max_participants,
        current_participants=0,
        created_by=new_event.created_by,
        group_id=new_event.group_id,
        created_at=new_event.created_at
    )


@app.get("/groups/{group_id}/events/", response_model=List[EventResponse])
async def get_group_events(group_id: str, db: Session = Depends(get_db)):
    """Получение списка событий в группе"""
    group = db.query(Group).filter(Group.group_id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )

    events = db.query(Event).filter(Event.group_id == group_id).all()
    result = []
    for event in events:
        current_participants = get_event_participants_count(db, event.event_id)
        result.append(EventResponse(
            event_id=event.event_id,
            title=event.title,
            description=event.description,
            event_type=event.event_type,
            date_time=event.date_time,
            location=event.location,
            max_participants=event.max_participants,
            current_participants=current_participants,
            created_by=event.created_by,
            group_id=event.group_id,
            created_at=event.created_at
        ))

    return result


# =============================================================================
# ЭНДПОИНТЫ ЗАПИСИ НА СОБЫТИЯ
# =============================================================================

@app.post("/events/{event_id}/register", response_model=RegistrationResponse)
async def register_for_event(
        event_id: str,
        reminder_settings: ReminderSettings = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Запись пользователя на событие"""

    if not reminder_settings:
        reminder_settings = ReminderSettings()

    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Событие не найдено"
        )

    # Проверяем, является ли пользователь участником группы
    if not is_group_member(db, event.group_id, current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы должны быть участником группы, чтобы записаться на событие"
        )

    # Проверяем, не записан ли уже пользователь
    existing_registration = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.user_id == current_user.user_id
    ).first()

    if existing_registration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже записаны на это событие"
        )

    # Обрабатываем в зависимости от типа события
    if event.event_type == 'limited_seats':
        return await _register_limited_seats(db, event, current_user.user_id)
    else:
        return await _register_unlimited(db, event, current_user.user_id, reminder_settings)


async def _register_limited_seats(db: Session, event: Event, user_id: str) -> RegistrationResponse:
    """Обработка записи на событие с ограниченным количеством мест"""

    current_participants = get_event_participants_count(db, event.event_id)

    # Проверяем наличие свободных мест
    if current_participants >= event.max_participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="На это событие нет свободных мест"
        )

    # Создаем регистрацию
    registration = EventRegistration(
        event_id=event.event_id,
        user_id=user_id,
        registration_type='confirmed'
    )
    db.add(registration)
    db.commit()

    return RegistrationResponse(
        success=True,
        message=f"Вы успешно записаны на событие '{event.title}'",
        registration_type="confirmed",
        event_id=event.event_id
    )


async def _register_unlimited(
        db: Session,
        event: Event,
        user_id: str,
        reminder_settings: ReminderSettings
) -> RegistrationResponse:
    """Обработка 'записи' на событие с неограниченным количеством мест"""

    # Создаем регистрацию типа "reminder"
    registration = EventRegistration(
        event_id=event.event_id,
        user_id=user_id,
        registration_type='reminder'
    )
    db.add(registration)
    db.commit()

    return RegistrationResponse(
        success=True,
        message=f"Создано напоминание о событии '{event.title}'",
        registration_type="reminder",
        event_id=event.event_id
    )


@app.delete("/events/{event_id}/unregister")
async def unregister_from_event(
        event_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Отмена записи или напоминания на событие"""

    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Событие не найдено"
        )

    # Удаляем регистрацию
    registration = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.user_id == current_user.user_id
    ).first()

    if not registration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы не были записаны на это событие"
        )

    db.delete(registration)
    db.commit()

    return {"message": "Запись на событие отменена"}


# =============================================================================
# БАЗОВЫЕ ЭНДПОИНТЫ
# =============================================================================

@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "EventList API работает!",
        "version": "2.0.0",
        "docs": "/docs",
        "status": "active"
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Проверка здоровья приложения и базы данных"""
    try:
        # Проверяем подключение к базе данных
        db.execute("SELECT 1")
        users_count = db.query(User).count()
        groups_count = db.query(Group).count()

        return {
            "status": "healthy",
            "database": "connected",
            "users_count": users_count,
            "groups_count": groups_count,
            "timestamp": datetime.now()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
