"""Test deduplicator normalization"""
import re

test_names = [
    "Xankəndi şəhərinin",
    "Kərkicahan qəsəbə",
    "Xankəndi",
]

suffixes = ['nin', 'nın', 'nun', 'nün', 'dan', 'dən', 'ta', 'tə', 'da', 'də']

def _normalize_name(name: str) -> str:
    """Нормализация имени для сравнения"""
    name = name.lower().strip()
    print(f"  After lower: '{name}'")
    
    # Удаляем пунктуацию
    name = re.sub(r'[^\w\s]', '', name)
    print(f"  After regex: '{name}' (len={len(name)})")
    
    # Удаляем суффиксы
    for suffix in suffixes:
        if name.endswith(suffix) and len(name) > len(suffix) + 3:
            name = name[:-len(suffix)]
            print(f"  After removing '{suffix}': '{name}'")
            break
    
    # Удаляем лишние пробелы
    name = re.sub(r'\s+', ' ', name).strip()
    print(f"  Final: '{name}' (len={len(name)})")
    
    return name

for test in test_names:
    print(f"\nTesting: '{test}'")
    result = _normalize_name(test)
    print(f"Result: '{result}' - Pass: {len(result) >= 3}")
