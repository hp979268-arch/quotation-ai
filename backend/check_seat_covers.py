import json
d = json.load(open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'r', encoding='utf-8'))
for item in d.get('stored_items',[]):
    if item.get('brand') == 'Kohler':
        name = item.get('name', '').lower()
        if any(x in name for x in ['pvc', 'uf seat', 'all colour', 'bidet']):
            print(f"{item.get('search_code')} -> {item.get('name')}")
