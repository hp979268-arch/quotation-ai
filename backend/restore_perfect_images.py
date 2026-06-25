import search_engine
import json

with open('c:/Movies/quotation-ai/quotation-ai/backup_march_state_june23/search_index_v2.json', 'r', encoding='utf-8') as f:
    old_data = json.load(f)
old_items_dict = {i['search_code']: i for i in old_data.get('stored_items', [])}

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    new_data = json.load(f)

for item in new_data.get('stored_items', []):
    code = item.get('search_code')
    if code in old_items_dict:
        # Restore EXACT images array from the perfect backup
        item['images'] = old_items_dict[code].get('images', [])

# Manually rebuild keyword index based on the 2903 items with fixed images
search_engine.load_index()
search_engine.stored_items = []
search_engine.keyword_index = {}
search_engine.vector_index = None

search_engine.add_to_index(None, new_data.get('stored_items', []))
print("Images perfectly restored and index rebuilt!")
