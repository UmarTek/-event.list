# api/moderation.py - полный исправленный код
"""
API endpoints для модерации
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import List, Optional  # ДОБАВЬТЕ ЭТОТ ИМПОРТ!
from datetime import datetime
from pydantic import BaseModel  # ДОБАВЬТЕ ЭТОТ ИМПОРТ!

from database import (
    get_db, User, Group, Event, ContentReport,
    GroupModerationRequest, ModerationAction, GroupMember
)
from auth.dependencies import get_current_user
from models.schemas import (
    GroupModerationUpdate, EventModerationUpdate, ContentReportCreate,
    UserBanRequest, ModerationFilter, GroupResponse, EventResponse,
    ModerationActionResponse
)
from models.enums import GroupStatus, EventStatus
from api.events import get_event_participants_count

router = APIRouter(prefix="/moderation", tags=["Модерация"])


# Схема для ContentReport
class ContentReportResponse(BaseModel):
    id: int
    reporter_id: str
    target_type: str
    target_id: str
    reason: str
    description: Optional[str] = None
    status: str
    moderator_id: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


def is_moderator(user: User) -> bool:
    """Проверка, является ли пользователь модератором"""
    return user.role in ['moderator', 'admin']


def is_admin(user: User) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user.role == 'admin'


def check_user_not_banned(user: User):
    """Проверка, не забанен ли пользователь"""
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


def log_moderation_action(
        db: Session,
        moderator_id: str,
        target_type: str,
        target_id: str,
        action_type: str,
        reason: Optional[str] = None
):
    """Логирование действия модерации"""
    action = ModerationAction(
        moderator_id=moderator_id,
        target_type=target_type,
        target_id=target_id,
        action_type=action_type,
        reason=reason
    )
    db.add(action)
    db.commit()


@router.get("/pending-groups", response_model=List[GroupResponse])
async def get_pending_groups(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получение списка групп, ожидающих модерации"""
    if not is_moderator(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только модераторы могут просматривать этот список"
        )

    pending_groups = db.query(Group).filter(Group.status == GroupStatus.PENDING).all()
    result = []
    for group in pending_groups:
        member_count = db.query(GroupMember).filter(GroupMember.group_id == group.group_id).count()
        result.append(GroupResponse(
            group_id=group.group_id,
            name=group.name,
            description=group.description,
            created_by=group.created_by,
            created_at=group.created_at,
            status=group.status,
            member_count=member_count,
            rejection_reason=group.rejection_reason
        ))
    return result


@router.get("/pending-events", response_model=List[EventResponse])
async def get_pending_events(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получение списка событий, ожидающих модерации"""
    if not is_moderator(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только модераторы могут просматривать этот список"
        )

    pending_events = db.query(Event).filter(Event.status == EventStatus.PENDING).all()
    result = []
    for event in pending_events:
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


@router.put("/groups/{group_id}")
async def moderate_group(
        group_id: str,
        moderation_data: GroupModerationUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Модерация группы"""
    if not is_moderator(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только модераторы могут модерировать группы"
        )

    group = db.query(Group).filter(Group.group_id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )

    group.status = moderation_data.status
    group.moderated_by = current_user.user_id
    group.moderated_at = datetime.now()

    if moderation_data.status == 'rejected' and moderation_data.rejection_reason:
        group.rejection_reason = moderation_data.rejection_reason
    elif moderation_data.status == 'banned' and moderation_data.rejection_reason:
        group.ban_reason = moderation_data.rejection_reason

    db.commit()

    # Создаем запись в GroupModerationRequest
    moderation_request = GroupModerationRequest(
        group_id=group_id,
        status=moderation_data.status,
        moderator_id=current_user.user_id,
        rejection_reason=moderation_data.rejection_reason,
        reviewed_at=datetime.now()
    )
    db.add(moderation_request)

    # Логируем действие
    log_moderation_action(
        db=db,
        moderator_id=current_user.user_id,
        target_type='group',
        target_id=group_id,
        action_type=f'{moderation_data.status}_group',
        reason=moderation_data.rejection_reason
    )

    db.commit()

    return {"message": f"Группа {moderation_data.status}", "group_id": group_id}


@router.put("/events/{event_id}")
async def moderate_event(
        event_id: str,
        moderation_data: EventModerationUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Модерация события"""
    if not is_moderator(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только модераторы могут модерировать события"
        )

    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Событие не найдено"
        )

    event.status = moderation_data.status
    event.moderated_by = current_user.user_id
    event.moderated_at = datetime.now()

    db.commit()

    # Логируем действие
    log_moderation_action(
        db=db,
        moderator_id=current_user.user_id,
        target_type='event',
        target_id=event_id,
        action_type=f'{moderation_data.status}_event',
        reason=moderation_data.reason
    )

    return {"message": f"Событие {moderation_data.status}", "event_id": event_id}


@router.post("/reports/")
async def create_report(
        report_data: ContentReportCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Создание жалобы на контент"""
    check_user_not_banned(current_user)

    report = ContentReport(
        reporter_id=current_user.user_id,
        target_type=report_data.target_type,
        target_id=report_data.target_id,
        reason=report_data.reason,
        description=report_data.description
    )
    db.add(report)
    db.commit()

    return {"message": "Жалоба создана успешно", "report_id": report.id}


@router.get("/reports", response_model=List[ContentReportResponse])
async def get_reports(
        status: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получение списка жалоб (только для модераторов)"""
    if not is_moderator(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только модераторы могут просматривать жалобы"
        )

    query = db.query(ContentReport)
    if status:
        query = query.filter(ContentReport.status == status)

    reports = query.order_by(ContentReport.created_at.desc()).all()

    # Преобразуем в Pydantic модель
    result = []
    for report in reports:
        result.append(ContentReportResponse(
            id=report.id,
            reporter_id=report.reporter_id,
            target_type=report.target_type,
            target_id=report.target_id,
            reason=report.reason,
            description=report.description,
            status=report.status,
            moderator_id=report.moderator_id,
            created_at=report.created_at,
            resolved_at=report.resolved_at
        ))
    return result


@router.put("/users/{user_id}/ban")
async def ban_user(
        user_id: str,
        ban_data: UserBanRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Блокировка пользователя (только для админов)"""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администраторы могут блокировать пользователей"
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    user.is_banned = ban_data.is_banned
    user.ban_reason = ban_data.ban_reason
    user.banned_until = ban_data.banned_until

    db.commit()

    # Логируем действие
    action_type = "ban_user" if ban_data.is_banned else "unban_user"
    log_moderation_action(
        db=db,
        moderator_id=current_user.user_id,
        target_type='user',
        target_id=user_id,
        action_type=action_type,
        reason=ban_data.ban_reason
    )

    return {"message": f"Пользователь {'заблокирован' if ban_data.is_banned else 'разблокирован'}", "user_id": user_id}


@router.get("/actions", response_model=List[ModerationActionResponse])
async def get_moderation_actions(
        filter_data: ModerationFilter = Depends(),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получение логов действий модерации"""
    if not is_moderator(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только модераторы могут просматривать логи модерации"
        )

    query = db.query(ModerationAction)

    if filter_data.status:
        query = query.filter(ModerationAction.action_type.like(f"%{filter_data.status}%"))

    if filter_data.target_type:
        query = query.filter(ModerationAction.target_type == filter_data.target_type)

    if filter_data.date_from:
        query = query.filter(ModerationAction.created_at >= filter_data.date_from)

    if filter_data.date_to:
        query = query.filter(ModerationAction.created_at <= filter_data.date_to)

    actions = query.order_by(ModerationAction.created_at.desc()).all()
    return actions