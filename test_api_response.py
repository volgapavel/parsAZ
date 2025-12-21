"""Test API response to see actual structure"""
import sys
import json
sys.path.insert(0, r'C:\Users\admin\MIPT\Sem3\Hackathon\parsAZ')

from api import process_article, ProcessRequest

# Test data
test_request = ProcessRequest(
    text="Xankəndi şəhərinin Kərkicahan qəsəbəsinə yola salınan köç ünvana çatıb",
    title="Xankəndi test",
    extract_relationships=True,
    classify_risks=True
)

print("Sending request...")
try:
    import asyncio
    result = asyncio.run(process_article(test_request))
    print("\n=== SUCCESS ===")
    print(f"Type: {type(result)}")
    print(f"\nEntities type: {type(result.entities)}")
    print(f"Entities: {result.entities}")
    print(f"\nEntities keys: {result.entities.keys() if hasattr(result.entities, 'keys') else 'N/A'}")
    
    # Проверка каждого типа
    for key, value in result.entities.items():
        print(f"\n{key}: {len(value)} items")
        if len(value) > 0:
            print(f"  First item: {value[0]}")
    
    # Конвертируем в JSON как это делает FastAPI
    import json
    from pydantic import BaseModel
    if isinstance(result, BaseModel):
        json_str = result.model_dump_json(indent=2)
        print("\n=== JSON OUTPUT ===")
        print(json_str)
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
