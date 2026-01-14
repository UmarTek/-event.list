# auth/__init__.py - исправленная версия
from .service import AuthService

# Не импортируем dependencies, если они не существуют
try:
    from .dependencies import get_current_user
except ImportError:
    pass

__all__ = ['AuthService' , 'get_current_user']