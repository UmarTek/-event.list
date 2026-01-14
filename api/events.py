"""API endpoints для событий"""


from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from database import get_db, User, Group, GroupMember, Event, EventRegistration
from auth.dependencies import get_current_user
from models.schemas import (
    EventCreate, EventResponse, ReminderSettings,
    RegistrationResponse
)
from models.enums import EventStatus, GroupStatus
from moderation_service import content_moderator

def get_event_participants_count(db: Session, event_id: str) -> int:
    """Получение количества участников события"""
    return db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.registration_type == 'confirmed'
    ).count()

router = APIRouter(prefix="/events", tags=["События"])

# Добавляем функции, которые нужны для работы events.py
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

def is_moderator(user: User) -> bool:
    """Проверка, является ли пользователь модератором"""
    return user.role in ['moderator', 'admin']

def check_user_not_banned(user: User):
    """Проверка, не забанен ли пользователь"""
    from datetime import datetime
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

def get_event_participants_count(db: Session, event_id: str) -> int:
    """Получение количества участников события"""
    return db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.registration_type == 'confirmed'
    ).count()

@router.post("/groups/{group_id}/events/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
        group_id: str,
        event_data: EventCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Создание нового события в группе"""

    check_user_not_banned(current_user)

    # Проверяем существование группы
    group = db.query(Group).filter(Group.group_id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )

    # Проверяем статус группы
    if group.status != GroupStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Группа не одобрена или забанена"
        )

    # Проверяем права доступа
    if not is_group_admin(db, group_id, current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администраторы группы могут создавать события"
        )

    # Проверка названия события на запрещённые слова
    title_check = content_moderator.check_text(event_data.title)
    if not title_check["is_clean"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Название события содержит запрещённый контент: {title_check['warning']}"
        )

    # Проверка описания события на запрещённые слова
    if event_data.description:
        desc_check = content_moderator.check_text(event_data.description)
        if not desc_check["is_clean"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Описание события содержит запрещённый контент: {desc_check['warning']}"
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

    # Автоматическая модерация событий
    status_to_set = EventStatus.APPROVED
    if title_check["banned_words_found"] or (event_data.description and desc_check["banned_words_found"]):
        status_to_set = EventStatus.PENDING

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
        group_id=group_id,
        status=status_to_set
    )

    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    current_participants = 0

    return EventResponse(
        event_id=event_id,
        title=new_event.title,
        description=new_event.description,
        event_type=new_event.event_type,
        date_time=new_event.date_time,
        location=new_event.location,
        max_participants=new_event.max_participants,
        current_participants=current_participants,
        created_by=new_event.created_by,
        group_id=new_event.group_id,
        status=new_event.status,
        created_at=new_event.created_at
    )


@router.get("/groups/{group_id}/events/", response_model=List[EventResponse])
async def get_group_events(
        group_id: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Получение списка событий в группе"""
    check_user_not_banned(current_user)

    group = db.query(Group).filter(Group.group_id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )

    # Проверяем права доступа
    is_member = is_group_member(db, group_id, current_user.user_id)
    is_group_moderator = is_moderator(current_user)

    if not is_member and not is_group_moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не являетесь участником этой группы"
        )

    # Для участников группы показываем все события (даже неодобренные)
    # Для модераторов показываем все
    # Для обычных пользователей показываем только одобренные
    if is_member or is_group_moderator:
        events = db.query(Event).filter(Event.group_id == group_id).all()
    else:
        events = db.query(Event).filter(Event.group_id == group_id, Event.status == EventStatus.APPROVED).all()

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
            status=event.status,
            created_at=event.created_at
        ))

    return result


@router.post("/{event_id}/register", response_model=RegistrationResponse)
async def register_for_event(
        event_id: str,
        reminder_settings: ReminderSettings = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Запись пользователя на событие"""

    check_user_not_banned(current_user)

    if not reminder_settings:
        reminder_settings = ReminderSettings()

    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Событие не найдено"
        )

    # Проверяем статус события
    if event.status != EventStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Событие не одобрено"
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


@router.delete("/{event_id}/unregister")
async def unregister_from_event(
        event_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Отмена записи или напоминания на событие"""

    check_user_not_banned(current_user)

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