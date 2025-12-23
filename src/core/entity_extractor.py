"""
entity_extractor_ner_ensemble.py

Ensemble NER extractor для азербайджанского языка с использованием:
1. Davlan/xlm-roberta-large-ner-hrl (основная модель: PER, ORG, LOC)
2. LocalDoc/private_ner_azerbaijani_v2 (дополнительная: даты, должности, адреса)

Преимущества:
- Двойная проверка основных сущностей (PER, ORG, LOC)
- Расширенные типы сущностей (даты, события, должности)
- Построение связей между сущностями через regex + вероятностный подход
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict, field
from collections import defaultdict

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline

logger = logging.getLogger(__name__)


@dataclass
@dataclass
class Entity:
    """Представление сущности"""
    name: str
    entity_type: str  # person, organization, location, position, date, event
    confidence: float
    context: str
    span: Tuple[int, int]  # (start, end)
    source: str  # 'davlan' или 'localdoc' или 'ensemble'
    
    def to_dict(self):
        return {
            "name": self.name,
            "confidence": float(self.confidence),  #  float32 → float
            "context": self.context,
            "type": self.entity_type,
            "source": self.source
        }

@dataclass
class Relationship:
    """Представление связи между сущностями"""
    source_entity: str
    target_entity: str
    relation_type: str  # works_for, located_in, manages, owns, etc
    confidence: float
    evidence: str  # текст, подтверждающий связь
    source: str  # regex, pattern, contextual


class NEREnsembleExtractor:
    """
    Ensemble NER extractor для азербайджанского.
    
    Использует две дополняющие друг друга BERT-модели:
    1. Davlan - широкое покрытие основных типов
    2. LocalDoc - специализированное извлечение на az
    """
    
    def __init__(self, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        """
        Инициализация обеих моделей.
        
        Args:
            device: 'cuda' или 'cpu'
        """
        self.device = device
        logger.info(f"Инициализация NER Ensemble на {device}...")
        
        # 1⃣ Основная модель: Davlan (3 типа: PER, ORG, LOC)
        try:
            self.davlan_model_name = "Davlan/xlm-roberta-large-ner-hrl"
            self.davlan_tokenizer = AutoTokenizer.from_pretrained(self.davlan_model_name)
            self.davlan_model = AutoModelForTokenClassification.from_pretrained(
                self.davlan_model_name
            ).to(self.device)
            self.davlan_nlp = pipeline(
                "ner",
                model=self.davlan_model,
                tokenizer=self.davlan_tokenizer,
                device=0 if device == "cuda" else -1,
                aggregation_strategy="simple"
            )
            logger.info("Davlan модель загружена успешно")
        except Exception as e:
            logger.error(f"Ошибка загрузки Davlan: {e}")
            self.davlan_nlp = None
        
        # 2⃣ Расширенная модель: LocalDoc (25 типов, az-специфичная)
        try:
            self.localdoc_model_name = "LocalDoc/private_ner_azerbaijani_v2"
            self.localdoc_tokenizer = AutoTokenizer.from_pretrained(self.localdoc_model_name)
            self.localdoc_model = AutoModelForTokenClassification.from_pretrained(
                self.localdoc_model_name
            ).to(self.device)
            self.localdoc_nlp = pipeline(
                "ner",
                model=self.localdoc_model,
                tokenizer=self.localdoc_tokenizer,
                device=0 if device == "cuda" else -1,
                aggregation_strategy="simple"
            )
            logger.info("LocalDoc модель загружена успешно")
        except Exception as e:
            logger.warning(f"LocalDoc модель недоступна (opt): {e}")
            self.localdoc_nlp = None
        
        # Словари для post-processing
        self.position_keywords = {
            "az": [
                "prezidenti", "baş naziri", "nazir", "müdür", "direktor",
                "səfir", "məsləhətçi", "hökuməti", "rəis", "başçı",
                "tapşırıqçı", "koordinator", "assistent", "şef", "mənas",
                "nümayəndəsi", "agenti", "əməkdaşı"
            ],
            "ru": [
                "президент", "премьер-министр", "министр", "директор",
                "посол", "советник", "глава", "глава компании", "руководитель"
            ]
        }
        
        self.location_keywords = {
            "az": [
                "bakı", "gəncə", "sumqayıt", "qəbələ", "shamakhi", 
                "polşa", "böyük britaniya", "abş", "misir", "suriyə", 
                "türkiyə", "irran", "rusiya", "çin", "hindistan",
                "fransiya", "almaniya", "italiya", "ispaniya", "portekiz"
            ],
            "en": [
                "poland", "britain", "united states", "egypt", "syria",
                "turkey", "iran", "russia", "china", "india",
                "france", "germany", "italy", "spain", "portugal"
            ]
        }
    def _extract_positions_from_context(self, entities: Dict, text: str) -> List:
      """Извлекаем должности из контекста сущностей"""
      positions = []
      person_names = [p.name for p in entities.get('persons', [])]
      
      # Паттерны для должностей
      position_patterns = [
          rf'({re.escape(person)}),\s*([\w\d\-]+\s+[\w\d\-]+(?:\s+[\w\d\-])?)' 
          for person in person_names[:5]  # Только первые 5 персон
      ]
      
      for pattern in position_patterns:
          for match in re.finditer(pattern, text):
              position = match.group(2).strip()
              # Фильтруем короткие и общие слова
              if len(position) > 4 and position not in ['dedik', 'olub', 'edib']:
                  positions.append(Entity(
                      name=position,
                      entity_type='position',
                      confidence=0.7,
                      context=match.group(0),
                      span=(match.start(), match.end()),
                      source='pattern'
                  ))
      
      return positions

    def extract_entities_davlan(self, text: str) -> List[Entity]:
      """ ФИКС: Davlan extraction с дебагом"""
      if not self.davlan_nlp:
          return []
      
      entities = []
      try:
          ner_results = self.davlan_nlp(text)
          print(f"Davlan raw result: {ner_results[:2] if ner_results else 'EMPTY'}")  # ДЕБАГ
          
          for result in ner_results:
              #  ФИКС: проверяем все возможные ключи
              entity_key = None
              for key in ['entity', 'entity_group', 'label', 'type']:
                  if key in result:
                      entity_key = key
                      break
              
              if not entity_key:
                  logger.warning(f"Нет entity ключа: {result.keys()}")
                  continue
                  
              entity_type_raw = result[entity_key].replace('B-', '').replace('I-', '').lower()
              
              type_mapping = {'per': 'person', 'org': 'organization', 'loc': 'location'}
              entity_type = type_mapping.get(entity_type_raw, entity_type_raw)
              
              entity = Entity(
                  name=result['word'].strip(),
                  entity_type=entity_type,
                  confidence=float(result.get('score', 0.5)),
                  context=text[max(0, result.get('start', 0)-50):result.get('end', len(text))+50],
                  span=(int(result.get('start', 0)), int(result.get('end', 0))),
                  source='davlan'
              )
              entities.append(entity)
              
      except Exception as e:
          logger.error(f"Ошибка в Davlan: {e}")
      
      return entities

    def extract_entities_localdoc(self, text: str) -> List[Entity]:
        """ ФИКС: LocalDoc extraction"""
        if not self.localdoc_nlp:
            return []
        
        entities = []
        try:
            ner_results = self.localdoc_nlp(text)
            print(f"LocalDoc raw: {ner_results[:2] if ner_results else 'EMPTY'}")  # ДЕБАГ
            
            for result in ner_results:
                entity_key = None
                for key in ['entity', 'entity_group', 'label', 'type']:
                    if key in result:
                        entity_key = key
                        break
                
                if not entity_key:
                    continue
                    
                entity_type_raw = result[entity_key].replace('B-', '').replace('I-', '').lower()
                
                type_mapping = {
                    'givenname': 'person', 'surname': 'person', 'firstname': 'person', 'lastname': 'person',
                    'city': 'location', 'location': 'location',
                    'date': 'date', 'time': 'date', 'age': 'date',
                    'organization': 'organization', 'org': 'organization'
                }
                
                entity_type = type_mapping.get(entity_type_raw, entity_type_raw)
                
                entity = Entity(
                    name=result['word'].strip(),
                    entity_type=entity_type,
                    confidence=float(result.get('score', 0.5)),
                    context=text[max(0, result.get('start', 0)-50):result.get('end', len(text))+50],
                    span=(int(result.get('start', 0)), int(result.get('end', 0))),
                    source='localdoc'
                )
                entities.append(entity)
                
        except Exception as e:
            logger.error(f"Ошибка в LocalDoc: {e}")
        
        return entities
    
    def extract_relationships(self, text: str, entities: Dict[str, List[Entity]]) -> List[Relationship]:
        """
        Построение связей между сущностями.
        
        Использует regex паттерны + контекстный анализ.
        """
        relationships = []
        
        # 1. Паттерн: "страна prezidenti ФИО" -> ФИО works_for страна
        pattern_country_leader = r'(\w+\s+\w*)\s+prezidenti\s+([А-ЯЕҚҝҹғҳҷҢҮҪҎҰҲҶҴҸҶҼҹҾҿ][а-яеқҝҹғҳҷҢҮҪҎҰҲҶҴҸҶҼҹҾҿ\s]+)'
        
        for match in re.finditer(pattern_country_leader, text, re.IGNORECASE):
            country = match.group(1).strip()
            person = match.group(2).strip()
            
            relationships.append(Relationship(
                source_entity=person,
                target_entity=country,
                relation_type="works_for",
                confidence=0.85,
                evidence=match.group(0),
                source="regex_leader"
            ))
        
        # 2. Паттерн: "ФИО, <должность> <организации>" -> ФИО works_for организация
        pattern_person_role = r'([А-ЯЕҚҝҹғҳҷҢҮҪҎҰҲҶҴҸҶҼҹҾҿ][а-яеқҝҹғҳҷҢҮҪҎҰҲҶҴҸҶҼҹҾҿ\s]+),\s+([\wәҹғҳҷҞҢҮҪҎҰҲҶҴҸҶҼҹҾҿ\s]+)(?:\s+(?:компаниясидә|банкида|министrəsində|şirkətində|məsələsində))'
        
        for match in re.finditer(pattern_person_role, text, re.IGNORECASE):
            person = match.group(1).strip()
            position = match.group(2).strip()
            
            relationships.append(Relationship(
                source_entity=person,
                target_entity=position,
                relation_type="has_position",
                confidence=0.8,
                evidence=match.group(0),
                source="regex_position"
            ))
        
        # 3. Паттерн: "X və Y şirkətləri" -> X, Y в одной категории
        pattern_companies = r'(\w+)\s+(?:və|іс|и)\s+(\w+)\s+(?:şirkətləri|kompaniyaları|bankları)'
        
        for match in re.finditer(pattern_companies, text, re.IGNORECASE):
            entity1 = match.group(1).strip()
            entity2 = match.group(2).strip()
            
            relationships.append(Relationship(
                source_entity=entity1,
                target_entity=entity2,
                relation_type="competitors",
                confidence=0.75,
                evidence=match.group(0),
                source="regex_competitors"
            ))
        
        return relationships
    
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Полное извлечение сущностей и связей.
        """
        # 1. Извлечение через обе модели
        davlan_entities = self.extract_entities_davlan(text)
        localdoc_entities = self.extract_entities_localdoc(text)

        # 2. Объединение и дедупликация
        all_entities = self._merge_entities(davlan_entities, localdoc_entities)

        # 3. Группировка по типам
        grouped_entities = self._group_entities(all_entities)

        # 4.  ИЗВЛЕЧЕНИЕ ДОЛЖНОСТЕЙ
        position_entities = self._extract_positions_from_context(grouped_entities, text)
        grouped_entities['position'] = position_entities

        # 5. Извлечение связей
        relationships = self.extract_relationships(text, grouped_entities)

        # 6. Построение графа знаний
        kg_nodes, kg_edges = self._build_knowledge_graph(grouped_entities, relationships)

        return {
            "entities": {
                "persons": grouped_entities.get('person', []),
                "organizations": grouped_entities.get('organization', []),
                "locations": grouped_entities.get('location', []),
                "dates": grouped_entities.get('date', []),
                "events": grouped_entities.get('event', []),
                "positions": grouped_entities.get('position', []),
                "all": all_entities,
            },
            "relationships": [asdict(r) for r in relationships],
            "knowledge_graph": {
                "nodes": kg_nodes,
                "edges": kg_edges,
            },
        }
    
    def _merge_entities(self, davlan: List[Entity], localdoc: List[Entity]) -> List[Entity]:
        """ ФИКС: безопасное объединение"""
        merged = {}
        
        all_entities = davlan + localdoc  # Просто конкатенируем
        
        for ent in all_entities:
            #  ФИКС: нормализуем типы
            type_map = {
                'per': 'person', 'givenname': 'person', 'surname': 'person',
                'firstname': 'person', 'lastname': 'person',
                'org': 'organization', 'organization': 'organization',
                'loc': 'location', 'city': 'location', 'location': 'location',
                'date': 'date', 'time': 'date', 'age': 'date'
            }
            norm_type = type_map.get(ent.entity_type.lower(), ent.entity_type)
            
            key = (ent.name.lower().strip(), norm_type)
            
            if key not in merged or ent.confidence > merged[key].confidence:
                merged[key] = ent
                merged[key].entity_type = norm_type  # ← нормализуем тип
        
        return list(merged.values())
    
    def _group_entities(self, entities: List[Entity]) -> Dict[str, List[Dict]]:
        """Группировка сущностей по типам"""
        grouped = defaultdict(list)
        
        for ent in entities:
            grouped[ent.entity_type].append(ent.to_dict())
        
        return dict(grouped)
    
    def _build_knowledge_graph(
        self, 
        grouped_entities: Dict[str, List], 
        relationships: List[Relationship]
    ) -> Tuple[Dict, List]:
        """Построение графа знаний из сущностей и связей"""
        
        nodes = {
            "persons": grouped_entities.get('person', []),
            "organizations": grouped_entities.get('organization', []),
            "locations": grouped_entities.get('location', []),
            "dates": grouped_entities.get('date', []),
            "events": grouped_entities.get('event', []),
            "positions": grouped_entities.get('position', []),
        }
        
        edges = [
            {
                "source": r.source_entity,
                "target": r.target_entity,
                "type": r.relation_type,
                "confidence": r.confidence,
                "evidence": r.evidence
            }
            for r in relationships
        ]
        
        return nodes, edges
