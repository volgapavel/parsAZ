"""
translator.py - Перевод текстов на английский (опционально)
"""


class Translator:
    """Перевод текстов"""

    def __init__(self):
        self.cache = {}
        try:
            from googletrans import Translator as GoogleTranslator
            self.translator = GoogleTranslator()
            self.available = True
        except ImportError:
            print("  googletrans не установлен, перевод отключен")
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
            result = self.translator.translate(text, src=source_lang, dest=target_lang)
            translated = result.text
            self.cache[cache_key] = translated
            return translated
        except Exception as e:
            print(f"Translation error: {e}")
            return text

