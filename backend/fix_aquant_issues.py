import json
import search_engine

index_path = 'c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json'
with open(index_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

bad_codes = {'1333 CM', '1333 PP', '1333 BM', '1333 RB', '11333 LM', '1080 MM L', '1112 X 95 X 500 MM'}

new_items = []
for item in data.get('stored_items', []):
    if item.get('search_code') not in bad_codes:
        new_items.append(item)

search_engine.stored_items = []
search_engine.keyword_index = {}
search_engine.vector_index = None
search_engine.add_to_index(None, new_items)
search_engine.save_index()
print(f"Removed {len(data.get('stored_items', [])) - len(new_items)} items. New total: {len(new_items)}")
