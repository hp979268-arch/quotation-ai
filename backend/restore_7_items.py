import json
import search_engine

found_codes = [
    "K-1286731",
    "K-27792IN-0",
    "K-28214-BL",
    "K-28786IN-0",
    "K-31014IN-0",
    "K-8705IN-0",
    "K-99992IN-0"
]

with open("c:/Movies/quotation-ai/quotation-ai/backup_march_state_june23/search_index_v2.json", "r", encoding='utf-8') as f:
    old_data = json.load(f)

old_items = {i.get('search_code'): i for i in old_data.get('stored_items', []) if i.get('brand') == 'Kohler'}

search_engine.load_index()

restored = 0
for code in found_codes:
    if code in old_items:
        item = old_items[code]
        item['source'] = "Kohler_PriceBook (June'26).pdf"
        search_engine.stored_items.append(item)
        restored += 1

print(f"Restored {restored} items.")
search_engine.save_index()
print("Index saved successfully.")
