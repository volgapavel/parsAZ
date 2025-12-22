"""
output_formatter.py - Форматирование и сохранение результатов
"""

import json
from typing import Dict, List


class OutputFormatter:
    """Форматирование результатов анализа"""

    def format_article_result(self, article_id: str, title: str, link: str, 
                              pub_date: str, entities: dict, risks: dict, 
                              relationships: List[Dict] = None,
                              knowledge_graph: dict = None):
        result = {
            "id": article_id,
            "title": title,
            "link": link,
            "pub_date": pub_date,
            "source": "",
            "entities": {
                "persons": entities.get("persons", []),
                "organizations": entities.get("organizations", []),
                "locations": entities.get("locations", []),
                "dates": entities.get("dates", []),
                "positions": entities.get("positions", []),
                "events": entities.get("events", [])
            },
            "relationships": relationships or [],  # ← СВЯЗИ!
            "risks": risks,
            "knowledge_graph": knowledge_graph or {"nodes": {}, "edges": []}
        }
        return result

    def to_json(self, results: List[Dict]) -> Dict:
        """Конвертировать результаты в JSON"""
        return {
            'summary': {
                'total_articles': len(results),
                'successful': sum(1 for r in results if 'error' not in r),
                'failed': sum(1 for r in results if 'error' in r),
            },
            'articles': results
        }

    def save_json_file(self, data: Dict, filename: str):
        """Сохранить результаты в JSON файл"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def print_console(self, results: List[Dict], limit: int = 3):
        """Вывести результаты в консоль"""
        print("\n" + "="*80)
        print("ПРИМЕРЫ РЕЗУЛЬТАТОВ (первые 3)")
        print("="*80)

        for result in results[:limit]:
            if 'error' in result:
                continue

            print(f"\n {result['title']}")
            print(f"   Персоны: {', '.join(result['entities']['persons']) or 'нет'}")
            print(f"   Организации: {', '.join(result['entities']['organizations']) or 'нет'}")
            print(f"   Локации: {', '.join(result['entities']['locations']) or 'нет'}")
            print(f"   Риск: {result['risks']['risk_level']} ({result['risks']['risk_score']:.2%})")
