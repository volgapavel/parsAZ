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

        # Группируем по первому слову
        groups = defaultdict(list)
        
        for entity in entity_list:
            name = self._normalize_name(entity.name if hasattr(entity, 'name') else entity['name'])
            if not name or len(name) < 3:
                continue
                
            key = name.split()[0]  # Группируем по первому слову
            groups[key].append(entity)

        # В каждой группе выбираем лучший
        merged = []
        for group_name, group_entities in groups.items():
            if len(group_entities) == 1:
                merged.append(group_entities[0])
                continue
            
            # Сортируем по confidence и длине (более полное имя = лучше)
            sorted_entities = sorted(
                group_entities, 
                key=lambda e: (
                    (e.confidence if hasattr(e, 'confidence') else e['confidence']),
                    -len(e.name if hasattr(e, 'name') else e['name'])
                ),
                reverse=True
            )
            
            # Первый — main, остальные — aliases
            main_entity = sorted_entities[0]
            aliases = [e.name if hasattr(e, 'name') else e['name'] for e in sorted_entities[1:]]
            
            # Добавляем aliases в атрибуты
            if hasattr(main_entity, 'attributes'):
                main_entity.attributes['aliases'] = aliases
            elif isinstance(main_entity, dict):
                main_entity['aliases'] = aliases
                
            merged.append(main_entity)

        return merged

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