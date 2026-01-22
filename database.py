"""
Упрощенный модуль для работы с базой данных
"""

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, ForeignKey, Enum, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
import enum
import os

Base = declarative_base()

# ENUM классы
class ModerationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    BANNED = "banned"
    DELETED = "deleted"

class UserRole(str, enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"

class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"

class ReportReason(str, enum.Enum):
    SPAM = "spam"
    ILLEGAL = "illegal"
    HARASSMENT = "harassment"
    SCAM = "scam"
    INAPPROPRIATE = "inappropriate"
    OTHER = "other"

class ContentType(str, enum.Enum):
    EVENT = "event"
    GROUP = "group"
    USER = "user"

class ModerationActionType(str, enum.Enum):
    APPROVE_GROUP = "approve_group"
    REJECT_GROUP = "reject_group"
    BAN_GROUP = "ban_group"
    APPROVE_EVENT = "approve_event"
    REJECT_EVENT = "reject_event"
    DELETE_EVENT = "delete_event"
    WARN_USER = "warn_user"
    BAN_USER = "ban_user"
    UNBAN_USER = "unban_user"

# Модели
class User(Base):
    __tablename__ = "users"
    user_id = Column(String(36), primary_key=True, index=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    name = Column(String(100), nullable=False)
    is_verified = Column(Boolean, default=False)
    role = Column(String(20), default='user')  # Изменено с Enum на String для простоты
    is_banned = Column(Boolean, default=False)
    ban_reason = Column(Text, nullable=True)
    banned_until = Column(DateTime, nullable=True)
    warning_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

class Group(Base):
    __tablename__ = "groups"
    group_id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    status = Column(String(20), default='pending')  # Изменено с Enum на String
    moderated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    moderated_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    is_featured = Column(Boolean, default=False)
    featured_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class GroupMember(Base):
    __tablename__ = "group_members"
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(String(36), ForeignKey("groups.group_id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    role = Column(String(20), default='member')
    joined_at = Column(DateTime, server_default=func.now())

class Event(Base):
    __tablename__ = "events"
    event_id = Column(String(36), primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(20), nullable=False)
    date_time = Column(DateTime, nullable=False)
    location = Column(String(255), nullable=True)
    max_participants = Column(Integer, nullable=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    group_id = Column(String(36), ForeignKey("groups.group_id"), nullable=False)
    status = Column(String(20), default='pending')  # Изменено с Enum на String
    moderated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    moderated_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    is_featured = Column(Boolean, default=False)
    featured_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class EventRegistration(Base):
    __tablename__ = "event_registrations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(36), ForeignKey("events.event_id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    registration_type = Column(String(20), nullable=False)
    registered_at = Column(DateTime, server_default=func.now())

class AuthCode(Base):
    __tablename__ = "auth_codes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

class ContentReport(Base):
    __tablename__ = "content_reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reporter_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    target_type = Column(String(20), nullable=False)  # Изменено с Enum на String
    target_id = Column(String(36), nullable=False)
    reason = Column(String(20), nullable=False)  # Изменено с Enum на String
    description = Column(Text, nullable=True)
    status = Column(String(20), default='pending')  # Изменено с Enum на String
    moderator_id = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)

class ModerationAction(Base):
    __tablename__ = "moderation_actions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    moderator_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    target_type = Column(String(20), nullable=False)  # Изменено с Enum на String
    target_id = Column(String(36), nullable=False)
    action_type = Column(String(20), nullable=False)  # Изменено с Enum на String
    reason = Column(Text, nullable=True)
    duration_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class GroupModerationRequest(Base):
    __tablename__ = "group_moderation_requests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(String(36), ForeignKey("groups.group_id"), nullable=False)
    status = Column(String(20), default='pending')
    moderator_id = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
# Глобальные переменные для engine и SessionLocal
_engine = None
_SessionLocal = None

# Инициализация
def init_database():
    global _engine, _SessionLocal
    
    if _SessionLocal is not None:
        return _SessionLocal  # Уже инициализировано
    
    db_file = "eventlist.db"
    db_exists = os.path.exists(db_file)

    _engine = create_engine(
        f"sqlite:///./{db_file}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    try:
        Base.metadata.create_all(bind=_engine)
        if db_exists:
            print("✅ База данных подключена")
        else:
            print("✅ База данных создана успешно")
    except Exception as e:
        print(f"❌ Ошибка создания базы данных: {e}")
        raise

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    # Создаем демо-админа только если БД была только что создана
    if not db_exists:
        add_demo_admin(_SessionLocal)

    return _SessionLocal

def add_demo_admin(SessionLocal):
    """Добавление демо-администратора"""
    db = SessionLocal()
    try:
        import uuid

        # Проверяем, есть ли администратор
        admin = db.query(User).filter(User.phone == "+79000000001").first()
        if not admin:
            admin = User(
                user_id=str(uuid.uuid4()),
                phone="+79000000001",
                name="System Admin",
                role="admin",
                is_verified=True
            )
            db.add(admin)

        # Демо-пользователь
        demo = db.query(User).filter(User.phone == "+79000000000").first()
        if not demo:
            demo = User(
                user_id=str(uuid.uuid4()),
                phone="+79000000000",
                name="Demo User",
                role="user",
                is_verified=True
            )
            db.add(demo)

        # Модератор для тестирования
        moderator = db.query(User).filter(User.phone == "+79000000002").first()
        if not moderator:
            moderator = User(
                user_id=str(uuid.uuid4()),
                phone="+79000000002",
                name="Test Moderator",
                role="moderator",
                is_verified=True
            )
            db.add(moderator)

        db.commit()
        print("✅ Созданы тестовые пользователи:")
        print("   - Администратор: +79000000001 (admin)")
        print("   - Модератор: +79000000002 (moderator)")
        print("   - Пользователь: +79000000000 (user)")
    except Exception as e:
        print(f"⚠️ Ошибка при добавлении тестовых пользователей: {e}")
        db.rollback()
    finally:
        db.close()

def get_db():
    """Dependency для получения сессии БД"""
    if _SessionLocal is None:
        init_database()
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()