import json

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data.get('stored_items', [])

finishes = {
    'CP':  {'label': 'Chrome Plated', 'price_1m': '575',  'price_15m': '690'},
    'G':   {'label': 'Gold',          'price_1m': '1700', 'price_15m': '1850'},
    'BRG': {'label': 'Brushed Rose Gold', 'price_1m': '1700', 'price_15m': '1850'},
    'BG':  {'label': 'Brushed Gold',  'price_1m': '1700', 'price_15m': '1850'},
    'GG':  {'label': 'Graphite Grey', 'price_1m': '1700', 'price_15m': '1850'},
    'MB':  {'label': 'Matt Black',    'price_1m': '1700', 'price_15m': '1850'},
    'RG':  {'label': 'Rose Gold',     'price_1m': '1700', 'price_15m': '1850'},
}

# Find template to keep source/category consistent
template = next((i for i in items if '30006' in i.get('search_code','') and i.get('brand') == 'Aquant'), None)

new_entries = []
for finish, info in finishes.items():
    # 30006 - 1.0 mtr
    entry_1 = {
        "text": f"30006 {finish} - Extendible Shower Hose (SS) - {info['label']}\nSize : 1.0 mtr\nMRP : ₹ {info['price_1m']}/-",
        "name": f"30006 {finish} - Extendible Shower Hose (SS) - {info['label']} (1.0 mtr)",
        "price": info['price_1m'],
        "variant_prices": {},
        "page": 19,
        "source": template['source'] if template else "Aquant Price List Vol 15. Feb 2026_Searchable",
        "images": [f"/static/images/Aquant/30006-30007 {finish}.png?v=9"],
        "brand": "Aquant",
        "category": template['category'] if template else "SHOWERING SYSTEMS",
        "base_code": "30006",
        "variant_code": finish,
        "search_code": f"30006 {finish}",
        "finish_label": info['label']
    }
    
    # 30007 - 1.5 mtr
    entry_2 = {
        "text": f"30007 {finish} - Extendible Shower Hose (SS) - {info['label']}\nSize : 1.5 mtr\nMRP : ₹ {info['price_15m']}/-",
        "name": f"30007 {finish} - Extendible Shower Hose (SS) - {info['label']} (1.5 mtr)",
        "price": info['price_15m'],
        "variant_prices": {},
        "page": 19,
        "source": template['source'] if template else "Aquant Price List Vol 15. Feb 2026_Searchable",
        "images": [f"/static/images/Aquant/30006-30007 {finish}.png?v=9"],
        "brand": "Aquant",
        "category": template['category'] if template else "SHOWERING SYSTEMS",
        "base_code": "30007",
        "variant_code": finish,
        "search_code": f"30007 {finish}",
        "finish_label": info['label']
    }
    
    new_entries.extend([entry_1, entry_2])

# Remove all 30006 and 30007 items
items_cleaned = [
    i for i in items
    if not (i.get('search_code','').startswith('30006') or i.get('search_code','').startswith('30007'))
]

# Add 14 new entries
items_cleaned.extend(new_entries)
data['stored_items'] = items_cleaned

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Removed old items. Added {len(new_entries)} separate items (30006 and 30007 variants).")
