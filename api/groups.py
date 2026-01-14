"""API endpoints для групп"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from database import get_db, User, Group, GroupMember
from auth.dependencies import get_current_user
from models.schemas import GroupCreate, GroupResponse
from models.enums import GroupStatus
from moderation_service import content_moderator

router = APIRouter(prefix="/groups", tags=["Группы"])

# Теперь импортируем все модули
try:
    from database import get_db, User, Group, GroupMember
except ImportError:
    print("⚠️ Ошибка импорта database модулей")

try:
    from dependencies import get_current_user  # ИЗМЕНИЛИ ЭТУ СТРОКУ
except ImportError:
    try:
        from auth.dependencies import get_current_user
    except ImportError:
        print("⚠️ Ошибка импорта get_current_user")

try:
    from models.schemas import GroupCreate, GroupResponse
    from models.enums import GroupStatus
except ImportError:
    print("⚠️ Ошибка импорта models модулей")

try:
    from moderation_service import content_moderator
    print("✅ moderation_service успешно импортирован")
except ImportError as e:
    print(f"⚠️ Ошибка импорта moderation_service: {e}")
    # Создаем заглушку
    class SimpleContentModerator:
        def check_text(self, text):
            return {"is_clean": True, "banned_words_found": [], "warning": None}
        def check_group_name(self, name):
            result = self.check_text(name)
            if len(name) < 3:
                result["is_clean"] = False
                result["warning"] = "Название слишком короткое"
            if len(name) > 100:
                result["is_clean"] = False
                result["warning"] = "Название слишком длинное"
            return result
        def check_description(self, desc):
            return self.check_text(desc)

    content_moderator = SimpleContentModerator()

router = APIRouter(prefix="/groups", tags=["Группы"])

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


@router.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создание новой группы с автоматической модерацией"""

    check_user_not_banned(current_user)

    # Проверка названия группы на запрещённые слова
    name_check = content_moderator.check_group_name(group_data.name)
    if not name_check["is_clean"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Название группы содержит запрещённый контент: {name_check['warning']}"
        )

    # Проверка описания группы на запрещённые слова
    if group_data.description:
        desc_check = content_moderator.check_description(group_data.description)
        if not desc_check["is_clean"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Описание группы содержит запрещённый контент: {desc_check['warning']}"
            )

    # Автоматическая модерация
    status_to_set = GroupStatus.PENDING
    if not name_check["banned_words_found"] and not (group_data.description and desc_check["banned_words_found"]):
        status_to_set = GroupStatus.APPROVED

    group_id = str(uuid.uuid4())
    new_group = Group(
        group_id=group_id,
        name=group_data.name,
        description=group_data.description,
        created_by=current_user.user_id,
        status=status_to_set
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

    # Создаём запрос на модерацию если нужна ручная проверка
    if status_to_set == GroupStatus.PENDING:
        mod_request = GroupModerationRequest(
            group_id=group_id,
            status='pending'
        )
        db.add(mod_request)
        db.commit()

    member_count = 1

    return GroupResponse(
        group_id=group_id,
        name=new_group.name,
        description=new_group.description,
        created_by=new_group.created_by,
        created_at=new_group.created_at,
        status=new_group.status,
        member_count=member_count
    )


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получение информации о группе"""
    check_user_not_banned(current_user)

    group = db.query(Group).filter(Group.group_id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Группа не найдена"
        )

    # Не показываем забаненные группы обычным пользователям
    if group.status == GroupStatus.BANNED and not is_moderator(current_user):
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
        status=group.status,
        member_count=member_count,
        rejection_reason=group.rejection_reason
    )


@router.get("/", response_model=List[GroupResponse])
async def get_all_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получение списка всех групп (только одобренных)"""
    check_user_not_banned(current_user)

    # Для обычных пользователей показываем только одобренные группы
    if not is_moderator(current_user):
        groups = db.query(Group).filter(Group.status == GroupStatus.APPROVED).all()
    else:
        # Модераторы видят все группы кроме забаненных
        groups = db.query(Group).filter(Group.status != GroupStatus.BANNED).all()

    result = []
    for group in groups:
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


@router.post("/{group_id}/join")
async def join_group(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Вступление пользователя в группу"""
    check_user_not_banned(current_user)

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