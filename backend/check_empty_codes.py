import json

index_path = 'c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json'
with open(index_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

count = 0
for item in data.get('stored_items', []):
    if item.get('brand') == 'Aquant':
        c = item.get('search_code', '').strip()
        bc = item.get('base_code', '').strip()
        if not c or not bc:
            print(f"Empty code found! Name: {item.get('name')}")
            count += 1
print(f"Total empty codes: {count}")
