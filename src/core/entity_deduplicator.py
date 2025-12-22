"""
entity_deduplicator.py - Дедупликация и нормализация сущностей
"""

import re
from typing import List, Dict, Any
from collections import defaultdict


class EntityDeduplicator:
    """Сжимает дубликаты сущностей на основе fuzzy matching"""

    def __init__(self):
        # Суффиксы для удаления
        self.suffixes = ['dir', 'dır', 'dur', 'dür', 'in', 'ın', 'un', 'ün',
                        'nin', 'nın', 'nun', 'nün', 'na', 'nə', 'da', 'də',
                        'ta', 'tə', 'dan', 'dən', 'tan', 'tən']
        
        # Аббревиатуры для сохранения
        self.abbreviations = {
            'p': 'Polad Həşimov',
            'ph': 'Polad Həşimov',
            'p.h': 'Polad Həşimov',
            'p.h.': 'Polad Həşimov',
            'phəşimov': 'Polad Həşimov',
        }

    def deduplicate_entities(self, entities: Dict[str, List[Any]]) -> Dict[str, List[Any]]:
        """
        Объединяет близкие сущности
        """
        # Обработка по типам
        for entity_type in ['persons', 'organizations']:
            entities[entity_type] = self._merge_similar_entities(
                entities[entity_type], 
                entity_type
            )
        
        # Фильтрация шума
        entities = self._filter_noise(entities)
        
        return entities

    def _merge_similar_entities(self, entity_list: List[Any], entity_type: str) -> List[Any]:
        """Мержим похожие имена"""
        if not entity_list:
            return []

        # Группируем по всем словам в имени (не только по первому)
        groups = defaultdict(list)
        name_to_entities = {}  # для отслеживания уже добавленных сущностей
        
        for entity in entity_list:
            name = self._normalize_name(entity.name if hasattr(entity, 'name') else entity['name'])
            if not name or len(name) < 3:
                continue
            
            # Создаем ключи по всем словам в имени
            words = name.split()
            if not words:
                continue
            
            # Сохраняем сущность с привязкой к её имени
            original_name = entity.name if hasattr(entity, 'name') else entity['name']
            name_to_entities[original_name] = entity
            
            # Добавляем в группы по каждому слову (для многословных имён)
            for word in words:
                if len(word) >= 2:  # игнорируем слишком короткие слова
                    groups[word].append(entity)

        # Объединяем сущности, которые имеют общие слова
        processed = set()
        merged = []
        
        for group_name, group_entities in groups.items():
            if not group_entities:
                continue
                
            for entity in group_entities:
                original_name = entity.name if hasattr(entity, 'name') else entity['name']
                if original_name in processed:
                    continue
                    
                # Находим все связанные сущности (имеющие общие слова)
                related = self._find_related_entities(entity, entity_list, processed)
                
                if len(related) == 1:
                    merged.append(related[0])
                    processed.add(original_name)
                    continue
                
                # Для группы связанных сущностей выбираем лучшую
                best_entity = self._select_best_entity(related)
                aliases = [e.name if hasattr(e, 'name') else e['name'] 
                          for e in related 
                          if (e.name if hasattr(e, 'name') else e['name']) != 
                             (best_entity.name if hasattr(best_entity, 'name') else best_entity['name'])]
                
                # Добавляем aliases
                if hasattr(best_entity, 'attributes'):
                    best_entity.attributes['aliases'] = aliases
                elif isinstance(best_entity, dict):
                    best_entity['aliases'] = aliases
                    
                merged.append(best_entity)
                
                # Отмечаем все связанные как обработанные
                for e in related:
                    processed.add(e.name if hasattr(e, 'name') else e['name'])

        return merged
    
    def _find_related_entities(self, entity: Any, entity_list: List[Any], processed: set) -> List[Any]:
        """Находит все сущности, связанные с данной (имеющие общие слова)"""
        entity_name = entity.name if hasattr(entity, 'name') else entity['name']
        entity_norm = self._normalize_name(entity_name)
        entity_words = set(entity_norm.split())
        
        related = []
        for other in entity_list:
            other_name = other.name if hasattr(other, 'name') else other['name']
            if other_name in processed:
                continue
                
            other_norm = self._normalize_name(other_name)
            other_words = set(other_norm.split())
            
            # Если есть общие слова или высокое сходство - считаем связанными
            if entity_words & other_words:  # есть пересечение
                related.append(other)
            else:
                # Дополнительная проверка на fuzzy match
                from difflib import SequenceMatcher
                ratio = SequenceMatcher(None, entity_norm, other_norm).ratio()
                if ratio >= 0.8:
                    related.append(other)
        
        return related if related else [entity]
    
    def _select_best_entity(self, entities: List[Any]) -> Any:
        """Выбирает лучшую сущность из группы (по confidence и длине имени)"""
        if len(entities) == 1:
            return entities[0]
        
        # Сортируем по confidence и длине (более полное имя = лучше)
        return sorted(
            entities,
            key=lambda e: (
                (e.confidence if hasattr(e, 'confidence') else e.get('confidence', 0)),
                len(e.name if hasattr(e, 'name') else e.get('name', ''))
            ),
            reverse=True
        )[0]

    def _normalize_name(self, name: str) -> str:
        """Нормализация имени для сравнения"""
        name = name.lower().strip()
        
        # Удаляем пунктуацию
        name = re.sub(r'[^\w\s]', '', name)
        
        # Удаляем суффиксы
        for suffix in self.suffixes:
            if name.endswith(suffix) and len(name) > len(suffix) + 3:
                name = name[:-len(suffix)]
        
        # Удаляем лишние пробелы
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name

    def _filter_noise(self, entities: Dict) -> Dict:
        """Удаляем шумные сущности"""
        
        # Фильтры по типам
        filters = {
            'persons': lambda e: len(self._normalize_name(e.name if hasattr(e, 'name') else e['name'])) >= 3,
            'organizations': lambda e: len(self._normalize_name(e.name if hasattr(e, 'name') else e['name'])) >= 4,
            'locations': lambda e: len(self._normalize_name(e.name if hasattr(e, 'name') else e['name'])) >= 3,
            'dates': lambda e: self._is_valid_date(e.name if hasattr(e, 'name') else e['name']),
        }

        for entity_type, filter_func in filters.items():
            if entity_type in entities:
                entities[entity_type] = [e for e in entities[entity_type] if filter_func(e)]
        
        return entities

    def _is_valid_date(self, date_str: str) -> bool:
        """Проверяем, что это действительно дата, а не число"""
        date_str = str(date_str)
        
        # ISO формат
        if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
            return True
        
        # День.месяц.год
        if re.match(r'\d{1,2}\.\d{1,2}\.\d{4}', date_str):
            return True
        
        # Числа <1900 — скорее всего не дата
        if date_str.isdigit() and int(date_str) < 1900:
            return False
        
        # Одно число без контекста — не дата
        if date_str.isdigit() and len(date_str) <= 2:
            return False
        
        return True