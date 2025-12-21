"""
data_loader.py - Загрузка и парсинг CSV файлов с новостями
"""

import pandas as pd
from dataclasses import dataclass
from typing import List
import logging

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """Структура новостной статьи"""
    id: int
    title: str
    content: str
    link: str
    pub_date: str
    created_at: str = None


class DataLoader:
    """Загрузка данных из CSV файлов"""
    
    REQUIRED_COLUMNS = ['id', 'title', 'content', 'link', 'pub_date']
    
    def load(self, csv_file: str) -> List[dict]:
        """
        Загрузить статьи из CSV файла
        
        Args:
            csv_file: Путь к CSV файлу
            
        Returns:
            Список словарей с статьями
        """
        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            raise IOError(f"Ошибка при чтении CSV: {e}")
        
        # Валидация колонок
        self._validate_columns(df)
        
        # Конвертация в словари
        articles = []
        for _, row in df.iterrows():
            article = {
                'id': int(row['id']),
                'title': str(row['title']).strip(),
                'content': str(row['content']).strip(),
                'link': str(row['link']).strip(),
                'pub_date': str(row['pub_date']).strip(),
            }
            
            if 'created_at' in df.columns:
                article['created_at'] = str(row['created_at']).strip()
            
            articles.append(article)
        
        logger.info(f"Загружено {len(articles)} статей из {csv_file}")
        return articles
    
    def _validate_columns(self, df: pd.DataFrame) -> None:
        """Проверить наличие требуемых колонок"""
        missing = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(
                f"Отсутствуют требуемые колонки: {missing}\n"
                f"Должны быть: {self.REQUIRED_COLUMNS}"
            )
