"""
risk_classifier.py - Классификация рисков
"""

from enum import Enum
from typing import Dict, List


class RiskLevel(Enum):
    """Уровни риска"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RiskClassifier:
    """Классификация репутационных и compliance рисков"""

    def __init__(self):
        self.risk_keywords = {
            'corruption': ['rüşvət', 'korrupsiya', 'payıcı', 'haram', 'qanunsuz'],
            'fraud': ['saxtakarlıq', 'aldatma', 'fırıldaq', 'yalan', 'saxta'],
            'sanctions': ['sanksiya', 'əngəllə', 'qadağan', 'məhdudlaş'],
            'legal_proceedings': ['məhkəmə', 'hüquq', 'ittiham', 'iddiaçı', 'mühakimə'],
            'bankruptcy': ['iflas', 'borc', 'ödəsiz', 'müflislik'],
            'organized_crime': ['mafiya', 'cinayət', 'qrupperovka', 'zorakılıq'],
            'conflict_of_interest': ['maraqların toqquşması', 'işərimdə'],
            'violations': ['qəza', 'ihlal', 'təxəl', 'pozulma'],
            'money_laundering': ['pul yıkama', 'gizli', 'şüphəli'],
            'management_changes': ['istefa', 'vəzifəsindən', 'təyin', 'müdür'],
        }

        self.risk_bigrams = {
            'corruption': [
                'rüşvət alıb', 'rüşvət verib', 'korrupsiya törədib',
                'rüşvətxor', 'rüşvət alarkən'
            ],
            'sanctions': [
                'sanksiya qoyulub', 'sanksiya tətbiq', 'sanksiya siyahısı',
                'qadağan edilib', 'məhdudlaşdırma qoyulub'
            ],
            'violations': [
                'qəza baş verib', 'qəza nəticəsində', 'qəzada ölüb',
                'partlayış olub', 'terror aktı'
            ],
            # Добавьте остальные...
        }

    def classify_risks(self, text: str, entities: Dict) -> Dict:
        """Классификация с учетом биграмм"""
        text_lower = text.lower()
        detected_risks = []

        # 1. Ключевые слова (как раньше)
        for risk_type, keywords in self.risk_keywords.items():
            count = sum(1 for kw in keywords if kw in text_lower)
            if count > 0:
                confidence = min(count * 0.2, 0.95)
                detected_risks.append({
                    'type': risk_type,
                    'confidence': confidence,
                    'keyword_matches': count
                })

        # 2. Биграммы (более точные)
        for risk_type, bigrams in self.risk_bigrams.items():
            count = sum(1 for bg in bigrams if bg in text_lower)
            if count > 0:
                detected_risks.append({
                    'type': risk_type,
                    'confidence': 0.85,  # Биграммы = высокая уверенность
                    'keyword_matches': count
                })

        # 3. Общий скор
        overall_score = sum(r['confidence'] for r in detected_risks) / len(detected_risks) if detected_risks else 0

        return {
            'detected_risks': detected_risks,
            'overall_risk_score': overall_score,
            'risk_level': self._get_risk_level(overall_score)
        }

    def _get_risk_level(self, score: float) -> str:
        """Определить уровень риска"""
        if score >= 0.75:
            return RiskLevel.CRITICAL.value
        elif score >= 0.5:
            return RiskLevel.HIGH.value
        elif score >= 0.25:
            return RiskLevel.MEDIUM.value
        else:
            return RiskLevel.LOW.value
