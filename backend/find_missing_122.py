import json

with open("c:/Movies/quotation-ai/quotation-ai/backup_march_state_june23/search_index_v2.json", "r", encoding='utf-8') as f:
    old_data = json.load(f)

with open("c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json", "r", encoding='utf-8') as f:
    new_data = json.load(f)

old_items = old_data.get('stored_items', [])
new_items = new_data.get('stored_items', [])

old_codes = {i.get('search_code'): i for i in old_items if i.get('brand') == 'Kohler'}
new_codes = {i.get('search_code'): i for i in new_items if i.get('brand') == 'Kohler'}

missing = set(old_codes.keys()) - set(new_codes.keys())
print(f"Total missing: {len(missing)}")

missing_details = [old_codes[c] for c in missing]
for i in missing_details[:10]:
    print(i.get('search_code'), "-", i.get('name')[:30])
