"""
Сервис для проверки контента на запрещённые слова
"""

import re
from typing import List, Dict, Tuple
from datetime import datetime, timedelta


class ContentModerator:
    def __init__(self):
        # Список запрещённых слов (можно расширять)
        self.banned_words = [
            # Экстремизм
            "терроризм", "экстремизм", "нацизм", "фашизм",

            # Дискриминация
            "нацист", "фашист", "расист", "гомофоб",

            # Незаконная деятельность
            "наркотики", "наркота", "героин", "кокаин", "марихуана",
            "оружие", "взрывчатка", "террорист",

            # Мошенничество
            "скам", "обман", "развод", "мошенничество",

            # Прочее
            "смерть", "убийство", "самоубийство", "насилие"
        ]

        # Регулярные выражения для более сложных проверок
        self.banned_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # Номера документов
            r'\b\d{16}\b',  # Номера карт
            r'\b\+?[78]\d{10}\b',  # Номера телефонов (подозрительные)
        ]

        # Слова, которые могут быть в контексте (разрешенные комбинации)
        self.allowed_combinations = [
            "борьба с терроризмом",
            "против экстремизма",
            "история фашизма",
            "против наркотиков",
        ]

    def check_text(self, text: str) -> Dict[str, any]:
        """
        Проверяет текст на наличие запрещённого контента

        Returns:
            dict: {
                "is_clean": bool,
                "banned_words_found": List[str],
                "warning": str или None
            }
        """
        if not text:
            return {"is_clean": True, "banned_words_found": [], "warning": None}

        text_lower = text.lower()
        found_words = []

        # Проверка на запрещённые слова
        for word in self.banned_words:
            if word in text_lower:
                # Проверяем, не является ли это разрешённой комбинацией
                is_allowed = False
                for allowed in self.allowed_combinations:
                    if allowed in text_lower and word in allowed:
                        is_allowed = True
                        break

                if not is_allowed:
                    found_words.append(word)

        # Проверка по регулярным выражениям
        for pattern in self.banned_patterns:
            if re.search(pattern, text):
                found_words.append(f"pattern: {pattern}")

        # Проверка на спам (многократное повторение)
        words = text_lower.split()
        if len(words) > 50:
            # Слишком длинный текст - возможный спам
            found_words.append("possible_spam: text_too_long")

        # Проверка на капслок
        if len(text) > 20 and text.isupper():
            found_words.append("warning: all_caps")

        if found_words:
            return {
                "is_clean": False,
                "banned_words_found": found_words,
                "warning": f"Найдены запрещённые слова: {', '.join(found_words[:3])}"
            }
        else:
            return {"is_clean": True, "banned_words_found": [], "warning": None}

    def check_group_name(self, name: str) -> Dict[str, any]:
        """Специальная проверка для названий групп"""
        result = self.check_text(name)

        # Дополнительные проверки для названий групп
        if len(name) < 3:
            result["is_clean"] = False
            result["warning"] = "Название группы слишком короткое"

        if len(name) > 100:
            result["is_clean"] = False
            result["warning"] = "Название группы слишком длинное"

        return result

    def check_description(self, description: str) -> Dict[str, any]:
        """Специальная проверка для описаний"""
        if not description:
            return {"is_clean": True, "banned_words_found": [], "warning": None}

        result = self.check_text(description)

        # Дополнительные проверки для описаний
        if len(description) > 2000:
            result["is_clean"] = False
            result["warning"] = "Описание слишком длинное"

        return result

    def check_event(self, title: str, description: str = None) -> Dict[str, any]:
        """Проверка события (название + описание)"""
        title_check = self.check_text(title)
        desc_check = self.check_text(description) if description else {"is_clean": True, "banned_words_found": []}

        all_found = title_check["banned_words_found"] + desc_check["banned_words_found"]

        return {
            "is_clean": title_check["is_clean"] and desc_check["is_clean"],
            "banned_words_found": all_found,
            "title_warnings": title_check.get("warning"),
            "description_warnings": desc_check.get("warning")
        }


# Глобальный экземпляр модератора
content_moderator = ContentModerator()