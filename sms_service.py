"""
Сервис для отправки SMS через msg.ovrx.ru
"""

import aiohttp
import os
from fastapi import HTTPException, status
from typing import Dict, Any
import json


class SMSService:
    def __init__(self):
        self.base_url = "https://msg.ovrx.ru"
        self.auth_endpoint = "/auth-code/sms"

    async def send_auth_code(self, phone: str, code: str) -> Dict[str, Any]:
        """
        Отправка кода авторизации на msg.ovrx.ru

        Формат запроса:
        POST https://msg.ovrx.ru/auth-code/sms
        {
            "phone": "79991234567",
            "code": "123456"
        }
        """
        try:
            # Нормализуем номер телефона
            normalized_phone = self._normalize_phone(phone)

            # Формируем payload
            payload = {
                "phone": normalized_phone,
                "code": code
            }

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "EventList/1.0"
            }

            print(f"📤 Отправка запроса на {self.base_url}{self.auth_endpoint}")
            print(f"📱 Данные: {json.dumps(payload, ensure_ascii=False)}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{self.base_url}{self.auth_endpoint}",
                        json=payload,
                        headers=headers,
                        timeout=30
                ) as response:

                    response_text = await response.text()
                    print(f"📥 Ответ от сервиса: Status {response.status}, Body: {response_text}")

                    if response.status == 200:
                        try:
                            result = await response.json()
                            return {
                                "success": True,
                                "status_code": response.status,
                                "data": result,
                                "message": "Код успешно отправлен через msg.ovrx.ru"
                            }
                        except:
                            # Если ответ не JSON, но статус 200
                            return {
                                "success": True,
                                "status_code": response.status,
                                "data": {"message": response_text},
                                "message": "Код отправлен"
                            }
                    else:
                        error_message = f"Ошибка отправки SMS: {response.status}"
                        try:
                            error_data = await response.json()
                            error_message = f"{error_message} - {error_data}"
                        except:
                            error_message = f"{error_message} - {response_text}"

                        return {
                            "success": False,
                            "status_code": response.status,
                            "error": error_message,
                            "response_body": response_text
                        }

        except aiohttp.ClientError as e:
            error_msg = f"Ошибка подключения к сервису SMS: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "status_code": 503
            }
        except Exception as e:
            error_msg = f"Неизвестная ошибка при отправке SMS: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "status_code": 500
            }

    def _normalize_phone(self, phone: str) -> str:
        """
        Нормализация номера телефона для msg.ovrx.ru

        Преобразует номер в формат: 79991234567 (без + и пробелов)
        """
        # Убираем все нецифровые символы
        cleaned = ''.join(c for c in phone if c.isdigit())

        # Обрабатываем разные форматы номеров
        if cleaned.startswith('7') and len(cleaned) == 11:
            # Уже в правильном формате (79123456789)
            return cleaned
        elif cleaned.startswith('8') and len(cleaned) == 11:
            # Российский номер (89123456789) -> 79123456789
            return '7' + cleaned[1:]
        elif cleaned.startswith('9') and len(cleaned) == 10:
            # Номер без кода страны (9123456789) -> 79123456789
            return '7' + cleaned
        elif len(cleaned) == 10:
            # Предполагаем, что это номер без 7 или 8
            return '7' + cleaned
        else:
            # Возвращаем очищенный номер как есть
            print(f"⚠️ Нестандартный формат номера: {phone} -> {cleaned}")
            return cleaned


# Глобальный экземпляр сервиса
sms_service = SMSService()