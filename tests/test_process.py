"""Test script to reproduce the error"""
import sys
sys.path.insert(0, r'C:\Users\admin\MIPT\Sem3\Hackathon\parsAZ')

from api import process_article, ProcessRequest

# Test data
test_request = ProcessRequest(
    text="Mingəçevirdə 52 yaşlı kişi aldığı xəsarətdən ölüb. İ.Baxışov xəstəxanada vəfat edib.",
    title="Mingəçevirdə hadisə",
    source="Report.az",
    extract_relationships=True,
    classify_risks=True
)

print("Sending request...")
try:
    import asyncio
    result = asyncio.run(process_article(test_request))
    print("Success!")
    print(result)
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
