"""
Pydantic схемы для валидации данных
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import List, Optional
from datetime import datetime
import re


class PhoneRequest(BaseModel):
    phone: str


class CodeVerification(BaseModel):
    phone: str
    code: str


class UserUpdate(BaseModel):
    name: str
    email: Optional[EmailStr] = None


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)


class EventCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    event_type: str
    date_time: datetime
    location: Optional[str] = None
    max_participants: Optional[int] = None


class ReminderSettings(BaseModel):
    remind_24h: bool = True
    remind_2h: bool = True
    remind_day: bool = True


# Модерация
class GroupModerationUpdate(BaseModel):
    status: str
    rejection_reason: Optional[str] = None

    @field_validator('status')
    def validate_status(cls, v):
        if v not in ['approved', 'rejected', 'banned']:
            raise ValueError('status must be one of: approved, rejected, banned')
        return v


class EventModerationUpdate(BaseModel):
    status: str
    reason: Optional[str] = None

    @field_validator('status')
    def validate_status(cls, v):
        if v not in ['approved', 'rejected']:
            raise ValueError('status must be one of: approved, rejected')
        return v


class ContentReportCreate(BaseModel):
    target_type: str
    target_id: str
    reason: str
    description: Optional[str] = None

    @field_validator('target_type')
    def validate_target_type(cls, v):
        if v not in ['event', 'group', 'user', 'comment']:
            raise ValueError('target_type must be one of: event, group, user, comment')
        return v

    @field_validator('reason')
    def validate_reason(cls, v):
        if v not in ['spam', 'illegal', 'harassment', 'scam', 'other']:
            raise ValueError('reason must be one of: spam, illegal, harassment, scam, other')
        return v


class UserBanRequest(BaseModel):
    is_banned: bool
    ban_reason: Optional[str] = None
    banned_until: Optional[datetime] = None


class ModerationFilter(BaseModel):
    status: Optional[str] = None
    target_type: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


# Ответы
class UserResponse(BaseModel):
    user_id: str
    phone: str
    email: Optional[str]
    name: str
    is_verified: bool
    role: str
    is_banned: bool
    created_at: datetime

    class Config:
        from_attributes = True


class GroupResponse(BaseModel):
    group_id: str
    name: str
    description: Optional[str]
    created_by: str
    created_at: datetime
    status: str
    member_count: int
    rejection_reason: Optional[str] = None


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
    status: str
    created_at: datetime


class RegistrationResponse(BaseModel):
    success: bool
    message: str
    registration_type: str
    event_id: str


class ModerationActionResponse(BaseModel):
    id: int
    moderator_id: str
    target_type: str
    target_id: str
    action_type: str
    reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True