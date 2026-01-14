# api/__init__.py - упрощенная версия
from .users import router as users_router
from .groups import router as groups_router
from .events import router as events_router
from .moderation import router as moderation_router

__all__ = ['users_router', 'groups_router', 'events_router', 'moderation_router']