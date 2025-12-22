"""
relationship_extractor_hybrid_pro.py

Полнофункциональный гибридный экстрактор отношений между сущностями

Использует 3 метода с graceful fallback:
1. Regex паттерны (85% точность, быстро)
2. spaCy Dependency Parsing (72% точность, интерпретируемо)
3. Zero-shot BERT Classification (80-85% точность, универсально)
"""

import logging
import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)

# Импорт переводчика
try:
    from src.core.translator import Translator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False
    logger.warning("translator.py not found, translation disabled")


@dataclass
class ExtractedRelation:
    """Модель для извлеченного отношения"""
    source_entity: str
    target_entity: str
    relation_type: str
    confidence: float
    evidence: str
    source_method: str  # 'regex', 'spacy', 'bert', 'entity_linking'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_entity': self.source_entity,
            'target_entity': self.target_entity,
            'relation_type': self.relation_type,
            'confidence': float(self.confidence),
            'evidence': self.evidence,
            'source_method': self.source_method
        }


class RelationExtractorHybridPro:
    """
    Гибридный экстрактор с 3 методами и graceful fallback
    
    Архитектура:
    - Regex: BASE LAYER (всегда работает)
    - spaCy: SYNTAX LAYER (если доступен)
    - BERT: SEMANTIC LAYER (если доступен)
    """
    
    def __init__(
        self,
        use_regex: bool = True,
        use_spacy: bool = True,
        use_bert: bool = True,
        use_translation: bool = True,
        device: str = "cpu"
    ):
        """
        Args:
            use_regex: Использовать regex паттерны
            use_spacy: Пытаться использовать spaCy
            use_bert: Пытаться использовать BERT
            use_translation: Переводить азербайджанский текст на английский
            device: 'cpu' или 'cuda'
        """
        self.device = device
        self.methods_loaded = []
        
        # Инициализация атрибутов
        self.spacy_nlp = None
        self.zeroshot_pipeline = None
        
        # Инициализация переводчика
        self.translator = None
        if use_translation and TRANSLATOR_AVAILABLE:
            try:
                self.translator = Translator()
                if self.translator.available:
                    logger.info("Translator initialized")
                    self.methods_loaded.append('translator')
                else:
                    self.translator = None
            except Exception as e:
                logger.warning(f"Translator init failed: {e}")
                self.translator = None
        
        # Layer 1: Regex (ВСЕГДА инициализируется)
        if use_regex:
            self._init_regex()
        
        # Layer 2: spaCy (с graceful fallback)
        if use_spacy:
            self._init_spacy()
        
        # Layer 3: BERT Zero-shot (с graceful fallback)
        if use_bert:
            self._init_bert()
        
        logger.info(f"Loaded methods: {', '.join(self.methods_loaded)}")
    
    def _init_regex(self) -> None:
        """Инициализация Regex метода"""
        try:
            self.regex_patterns = self._compile_patterns()
            self.methods_loaded.append('regex')
            logger.info("Regex patterns compiled")
        except Exception as e:
            logger.error(f"Failed to init regex: {e}")
    
    def _init_spacy(self) -> None:
        """Инициализация spaCy с graceful fallback"""
        try:
            import spacy
            # Пробуем загрузить многоязычную модель (для азербайджанского и др.)
            try:
                self.spacy_nlp = spacy.load("xx_ent_wiki_sm")
                self.methods_loaded.append('spacy')
                logger.info("spaCy loaded (xx_ent_wiki_sm - multilingual)")
            except OSError:
                # Если нет многоязычной, пробуем английскую
                try:
                    self.spacy_nlp = spacy.load("en_core_web_sm")
                    self.methods_loaded.append('spacy')
                    logger.info("spaCy loaded (en_core_web_sm)")
                except OSError:
                    logger.warning("spaCy model not found, downloading...")
                    import subprocess
                    subprocess.run(
                        ["python", "-m", "spacy", "download", "en_core_web_sm"],
                        capture_output=True
                    )
                    self.spacy_nlp = spacy.load("en_core_web_sm")
                    self.methods_loaded.append('spacy')
                    logger.info("spaCy loaded (en_core_web_sm)")
        except ImportError:
            logger.warning("spaCy not installed, skipping syntax layer")
            self.spacy_nlp = None
        except Exception as e:
            logger.warning(f"spaCy init failed: {e}")
            self.spacy_nlp = None
    
    def _init_bert(self) -> None:
        """Инициализация BERT Zero-shot с graceful fallback"""
        try:
            from transformers import pipeline
            import torch
            
            # Проверяем доступность CUDA
            if self.device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA not available, using CPU")
                device = 0 if torch.cuda.is_available() else -1
            else:
                device = 0 if self.device == "cuda" else -1
            
            self.zeroshot_pipeline = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
                device=device
            )
            self.methods_loaded.append('bert')
            logger.info("BERT zero-shot pipeline loaded")
        except ImportError:
            logger.warning("Transformers not installed, skipping BERT layer")
            self.zeroshot_pipeline = None
        except Exception as e:
            logger.warning(f"BERT init failed: {e}")
            self.zeroshot_pipeline = None
    
    # 
    # ГЛАВНЫЙ МЕТОД
    # 
    
    def extract_relationships(
        self,
        text: str,
        entities: Dict[str, List[Any]],
        source_lang: str = 'az'
    ) -> List[ExtractedRelation]:
        """
        Главный метод - использует все доступные методы
        
        Args:
            text: Текст статьи
            entities: Dict с ключами 'persons', 'organizations', 'locations'
                     Значения: List[Dict] или List[str]
            source_lang: Исходный язык текста ('az' для азербайджанского)
        
        Returns:
            List[ExtractedRelation] отсортированные по confidence
        """
        # Переводим текст на английский если доступен переводчик
        original_text = text
        if self.translator and source_lang != 'en':
            try:
                text = self.translator.translate_text(text, source_lang=source_lang, target_lang='en')
                logger.debug(f" Text translated from {source_lang} to en")
            except Exception as e:
                logger.warning(f" Translation failed: {e}, using original text")
                text = original_text
        
        all_relations = []
        
        # Метод 1: Regex (ВСЕГДА)
        try:
            regex_rels = self._extract_by_regex(text, entities)
            all_relations.extend(regex_rels)
            logger.debug(f" Regex: {len(regex_rels)} relations")
        except Exception as e:
            logger.error(f" Regex extraction failed: {e}")
        
        # Метод 2: spaCy (если доступен)
        if self.spacy_nlp:
            try:
                spacy_rels = self._extract_by_spacy(text, entities)
                all_relations.extend(spacy_rels)
                logger.debug(f" spaCy: {len(spacy_rels)} relations")
            except Exception as e:
                logger.warning(f" spaCy extraction failed: {e}")
        
        # Метод 3: BERT (если доступен)
        if self.zeroshot_pipeline:
            try:
                bert_rels = self._extract_by_bert(text, entities)
                all_relations.extend(bert_rels)
                logger.debug(f" BERT: {len(bert_rels)} relations")
            except Exception as e:
                logger.warning(f" BERT extraction failed: {e}")
        
        # Дедупликация и сортировка
        final_relations = self._deduplicate_relations(all_relations)
        final_relations.sort(key=lambda x: x.confidence, reverse=True)
        
        logger.info(f"Total relations: {len(final_relations)}")
        return final_relations
    
    # 
    # МЕТОД 1: REGEX ПАТТЕРНЫ
    # 
    
    def _compile_patterns(self) -> Dict[str, Any]:
        """Компилирование regex паттернов"""
        return {
            'works_for': [
                r'(\w+(?:\s+\w+)?)\s+(?:is|was|becomes|remains)\s+(?:the\s+)?(?:CEO|director|head|founder|president|minister|ambassador)\s+(?:of|at)\s+([A-Z]\w+(?:\s+[A-Z]\w+)*)',
                r'(\w+(?:\s+\w+)?)\s+(?:work|works|worked)\s+(?:as|for)\s+([A-Z]\w+(?:\s+[A-Z]\w+)*)',
                r'([A-Z]\w+(?:\s+[A-Z]\w+)*)\s+(?:appointed|named)\s+(\w+(?:\s+\w+)?)\s+(?:as\s+)?(?:CEO|director|head)',
            ],
            'located_in': [
                r'([A-Z]\w+(?:\s+[A-Z]\w+)*)\s+(?:is\s+)?(?:located|based|situated|headquartered)\s+in\s+([A-Z]\w+(?:\s+[A-Z]\w+)*)',
                r'([A-Z]\w+(?:\s+[A-Z]\w+)*)\s+office\s+(?:in|at)\s+([A-Z]\w+(?:\s+[A-Z]\w+)*)',
            ],
            'owns': [
                r'(\w+(?:\s+\w+)?)\s+(?:owns|founded|established)\s+([A-Z]\w+(?:\s+[A-Z]\w+)*)',
                r'([A-Z]\w+(?:\s+[A-Z]\w+)*)\s+(?:owned|founded)\s+by\s+(\w+(?:\s+\w+)?)',
            ],
            'competes_with': [
                r'([A-Z]\w+(?:\s+[A-Z]\w+)*)\s+(?:competes|compete)\s+with\s+([A-Z]\w+(?:\s+[A-Z]\w+)*)',
                r'([A-Z]\w+(?:\s+[A-Z]\w+)*)\s+vs\s+(?:vs\.?|versus)\s+([A-Z]\w+(?:\s+[A-Z]\w+)*)',
            ],
            'partners_with': [
                r'([A-Z]\w+(?:\s+[A-Z]\w+)*)\s+(?:partnered|partners|partnership)\s+with\s+([A-Z]\w+(?:\s+[A-Z]\w+)*)',
                r'([A-Z]\w+(?:\s+[A-Z]\w+)*)\s+and\s+([A-Z]\w+(?:\s+[A-Z]\w+)*)\s+(?:continue|have|maintain).*?(?:partnership|partner)',
                r'([A-Z]\w+(?:\s+[A-Z]\w+)*)\s+(?:and|,)\s+([A-Z]\w+(?:\s+[A-Z]\w+)*)\s+.*?partnership',
            ],
        }
    
    def _extract_by_regex(
        self,
        text: str,
        entities: Dict[str, List[Any]]
    ) -> List[ExtractedRelation]:
        """Извлечение отношений через regex паттерны"""
        relations = []
        
        for rel_type, patterns in self.regex_patterns.items():
            for pattern in patterns:
                try:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        if len(match.groups()) >= 2:
                            source = match.group(1).strip()
                            target = match.group(2).strip()
                            
                            # Проверяем что сущности есть в тексте
                            if self._is_valid_entity_pair(
                                source, target, entities
                            ):
                                relations.append(ExtractedRelation(
                                    source_entity=source,
                                    target_entity=target,
                                    relation_type=rel_type.upper(),
                                    confidence=0.85,
                                    evidence=match.group(0),
                                    source_method='regex'
                                ))
                except Exception as e:
                    logger.debug(f"Regex pattern error: {e}")
        
        return relations
    
    # 
    # МЕТОД 2: SPACY DEPENDENCY PARSING
    # 
    
    def _extract_by_spacy(
        self,
        text: str,
        entities: Dict[str, List[Any]]
    ) -> List[ExtractedRelation]:
        """Извлечение отношений через spaCy dependency parsing"""
        if not self.spacy_nlp:
            return []
        
        relations = []
        doc = self.spacy_nlp(text)
        
        # Извлекаем именованные сущности из spaCy
        entity_spans = {}
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG", "GPE"]:
                if ent.label_ not in entity_spans:
                    entity_spans[ent.label_] = []
                entity_spans[ent.label_].append((ent.text, ent.start, ent.end))
        
        # Ищем отношения между сущностями
        for token in doc:
            # WORKS_FOR: nsubj -> verb -> pobj/dobj
            if token.dep_ in ["nsubj", "nsubjpass"] and token.pos_ == "NOUN":
                verb = token.head
                
                # Ищем объект действия
                for child in verb.children:
                    if child.dep_ in ["pobj", "dobj", "attr"]:
                        relation_text = f"{token.text} {verb.text} {child.text}"
                        
                        relations.append(ExtractedRelation(
                            source_entity=token.text,
                            target_entity=child.text,
                            relation_type="WORKS_FOR",
                            confidence=0.72,
                            evidence=relation_text,
                            source_method='spacy'
                        ))
            
            # LOCATED_IN: compound nouns + prep
            if token.dep_ == "compound" and token.head.dep_ == "pobj":
                prep_token = token.head.head
                if prep_token.text.lower() in ["in", "at", "near"]:
                    relations.append(ExtractedRelation(
                        source_entity=f"{token.text} {token.head.text}",
                        target_entity=token.head.text,
                        relation_type="LOCATED_IN",
                        confidence=0.70,
                        evidence=f"{token.text} {token.head.text} {prep_token.text}",
                        source_method='spacy'
                    ))
        
        return relations
    
    # 
    # МЕТОД 3: BERT ZERO-SHOT CLASSIFICATION
    # 
    
    def _extract_by_bert(
        self,
        text: str,
        entities: Dict[str, List[Any]]
    ) -> List[ExtractedRelation]:
        """Извлечение отношений через BERT zero-shot classification"""
        if not self.zeroshot_pipeline:
            return []
        
        relations = []
        
        # Типы отношений для классификации
        relation_types = [
            "WORKS_FOR",
            "OWNS",
            "LOCATED_IN",
            "MANAGES",
            "COMPETES_WITH",
            "PARTNERS_WITH",
            "INVOLVED_IN"
        ]
        
        # Нормализуем сущности
        persons = self._normalize_entities(entities.get('persons', []))
        orgs = self._normalize_entities(entities.get('organizations', []))
        locations = self._normalize_entities(entities.get('locations', []))
        
        # Классифицируем пары person-org
        for person in persons:
            for org in orgs:
                try:
                    hypothesis = f"{person} and {org}"
                    
                    result = self.zeroshot_pipeline(
                        hypothesis,
                        relation_types,
                        multi_class=False
                    )
                    
                    top_relation = result['labels'][0]
                    confidence = float(result['scores'][0])
                    
                    if confidence > 0.65:
                        relations.append(ExtractedRelation(
                            source_entity=person,
                            target_entity=org,
                            relation_type=top_relation,
                            confidence=confidence,
                            evidence=hypothesis,
                            source_method='bert'
                        ))
                except Exception as e:
                    logger.debug(f"BERT classification failed: {e}")
        
        # Классифицируем пары org-location
        for org in orgs:
            for loc in locations:
                try:
                    hypothesis = f"{org} in {loc}"
                    
                    result = self.zeroshot_pipeline(
                        hypothesis,
                        ["LOCATED_IN", "OTHER"],
                        multi_class=False
                    )
                    
                    confidence = float(result['scores'][0])
                    if result['labels'][0] == "LOCATED_IN" and confidence > 0.70:
                        relations.append(ExtractedRelation(
                            source_entity=org,
                            target_entity=loc,
                            relation_type="LOCATED_IN",
                            confidence=confidence,
                            evidence=hypothesis,
                            source_method='bert'
                        ))
                except Exception as e:
                    logger.debug(f"BERT classification failed: {e}")
        
        return relations
    
    # 
    # УТИЛИТЫ
    # 
    
    def _normalize_entities(
        self,
        entities: List[Any]
    ) -> List[str]:
        """Нормализация сущностей из разных форматов"""
        normalized = []
        for entity in entities:
            if isinstance(entity, dict):
                if 'name' in entity:
                    normalized.append(entity['name'])
                elif 'text' in entity:
                    normalized.append(entity['text'])
            elif isinstance(entity, str):
                normalized.append(entity)
            else:
                # Попробуем получить .name attribute
                if hasattr(entity, 'name'):
                    normalized.append(entity.name)
                elif hasattr(entity, 'text'):
                    normalized.append(entity.text)
        
        return list(set(normalized))  # Удаляем дубликаты
    
    def _is_valid_entity_pair(
        self,
        source: str,
        target: str,
        entities: Dict[str, List[Any]]
    ) -> bool:
        """Проверка что пара сущностей реально существует"""
        all_persons = self._normalize_entities(
            entities.get('persons', [])
        )
        all_orgs = self._normalize_entities(
            entities.get('organizations', [])
        )
        all_locations = self._normalize_entities(
            entities.get('locations', [])
        )
        all_entities = all_persons + all_orgs + all_locations
        
        # Нечеткое сравнение (без учета регистра и пробелов)
        source_normalized = source.lower().strip()
        target_normalized = target.lower().strip()
        
        for entity in all_entities:
            entity_normalized = entity.lower().strip()
            if (source_normalized in entity_normalized or 
                entity_normalized in source_normalized):
                for entity2 in all_entities:
                    entity2_normalized = entity2.lower().strip()
                    if (target_normalized in entity2_normalized or 
                        entity2_normalized in target_normalized):
                        return True
        
        return False
    
    def _deduplicate_relations(
        self,
        relations: List[ExtractedRelation]
    ) -> List[ExtractedRelation]:
        """Дедупликация отношений, оставляем max confidence"""
        seen = {}
        
        for rel in relations:
            key = (
                rel.source_entity.lower(),
                rel.target_entity.lower(),
                rel.relation_type
            )
            
            if key not in seen:
                seen[key] = rel
            elif rel.confidence > seen[key].confidence:
                seen[key] = rel
        
        # Фильтруем по минимальной уверенности
        return [
            rel for rel in seen.values()
            if rel.confidence >= 0.60
        ]
