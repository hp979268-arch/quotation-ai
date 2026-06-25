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

template = next((i for i in items if '30006' in i.get('search_code','') and i.get('brand') == 'Aquant'), None)

new_entries = []
for finish, info in finishes.items():
    new_code = f"30006-30007 {finish}"
    desc = f"Extendible Shower Hose (SS) - {info['label']}\nSize : 1.0 mtr / 1.5 mtr\nMRP : ₹ {info['price_1m']}/- (1.0 mtr) | ₹ {info['price_15m']}/- (1.5 mtr)"
    entry = {
        "text": f"30006 30007 {new_code}\n{new_code} - {desc}",
        "name": f"{new_code} - Extendible Shower Hose (SS) - {info['label']}",
        "price": info['price_1m'],
        "variant_prices": {"1.5 mtr": info['price_15m']},
        "page": 19,
        "source": template['source'] if template else "Aquant Price List Vol 15. Feb 2026_Searchable",
        "images": [f"/static/images/Aquant/30006-30007%20{finish}.png?v=11"],
        "brand": "Aquant",
        "category": template['category'] if template else "SHOWERING SYSTEMS",
        "base_code": "30006-30007",
        "variant_code": finish,
        "full_code": new_code,
        "search_code": new_code,
        "finish_label": info['label']
    }
    new_entries.append(entry)

items_cleaned = [
    i for i in items
    if not (i.get('search_code','').startswith('30006') or i.get('search_code','').startswith('30007'))
]

items_cleaned.extend(new_entries)
data['stored_items'] = items_cleaned

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    
print("7 Joint entries recreated with %20 in image path.")
