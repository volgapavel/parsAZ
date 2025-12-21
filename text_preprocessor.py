"""
text_preprocessor.py - Предобработка текста на азербайджанском
"""

import re
import unicodedata


class TextPreprocessor:
    """Очистка и нормализация текста"""

    def __init__(self):
        self.stop_words_az = {
            'və', 'bir', 'bu', 'ki', 'o', 'biz', 'siz', 'onlar',
            'mən', 'sen', 'o', 'biz', 'siz', 'onlar',
            'haqqında', 'üçün', 'ilə', 'də', 'dən', 'az',
            'edin', 'oldu', 'olur', 'edər', 'edib'
        }

    def preprocess(self, text: str) -> str:
        """Полная предобработка текста"""
        # Нормализация
        text = self.clean_text(text)
        # Без удаления стоп-слов для NER
        return text

    def clean_text(self, text: str) -> str:
        """Очистка текста"""
        if not text:
            return ""

        # Нормализация Unicode
        text = unicodedata.normalize('NFKC', text)

        # Удаление лишних пробелов
        text = re.sub(r'\s+', ' ', text)

        # Удаление спецсимволов но оставляем пунктуацию
        text = re.sub(r'[^\w\s\-\.!?,.;:]', '', text)

        return text.strip()

    def split_sentences(self, text: str) -> list:
        """Разбиение на предложения"""
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
