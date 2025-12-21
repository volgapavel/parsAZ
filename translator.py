"""
translator.py - Перевод текстов на английский (опционально)
"""


class Translator:
    """Перевод текстов"""

    def __init__(self):
        self.cache = {}
        try:
            from google_trans_new import google_translator
            self.translator = google_translator()
            self.available = True
        except ImportError:
            print("⚠️  google-trans-new не установлен, перевод отключен")
            self.available = False

    def translate_text(self, text: str, source_lang='az', target_lang='en') -> str:
        """Перевести текст"""
        if not self.available or not text:
            return text

        # Кэш
        cache_key = f"{text[:50]}_{target_lang}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            result = self.translator.translate(text, source_language=source_lang, target_language=target_lang)
            self.cache[cache_key] = result
            return result
        except:
            return text
