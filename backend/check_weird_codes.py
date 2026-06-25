import json
d = json.load(open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'r', encoding='utf-8'))
for item in d.get('stored_items',[]):
    code = item.get('search_code', '')
    if code in ['1434-600 MM', '1000 MM L', '1160 MM L']:
        print(f"{code} -> {item.get('name')}")
