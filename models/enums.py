"""
Enum'ы для типов данных
"""

from enum import Enum


class UserRole(str, Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class GroupStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    BANNED = "banned"


class EventStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EventType(str, Enum):
    LIMITED_SEATS = "limited_seats"
    UNLIMITED = "unlimited"


class RegistrationType(str, Enum):
    CONFIRMED = "confirmed"
    REMINDER = "reminder"


class ReportReason(str, Enum):
    SPAM = "spam"
    ILLEGAL = "illegal"
    HARASSMENT = "harassment"
    SCAM = "scam"
    OTHER = "other"


class TargetType(str, Enum):
    EVENT = "event"
    GROUP = "group"
    USER = "user"
    COMMENT = "comment"