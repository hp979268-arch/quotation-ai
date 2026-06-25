"""
Bump image cache version in search_index_v2.json for all
fixed Kohler trim+valve images so browser cache is busted.
"""
import json, re

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data.get('stored_items', [])

with open('backend/trim_valve_products.json') as f:
    tv_data = json.load(f)
tv_codes = set(tv_data.get('codes', []))

updated = 0
for item in items:
    if not isinstance(item, dict):
        continue
    if 'kohler' not in item.get('brand', '').lower():
        continue
    sc = item.get('search_code', '')
    cat = item.get('category', '').lower()
    is_tv = (
        sc in tv_codes or 'in-wall' in cat or 'concealed' in cat or
        '4nd' in sc.lower() or '4fs' in sc.lower() or '4fp' in sc.lower()
    )
    if not is_tv:
        continue
    imgs = item.get('images', [])
    new_imgs = []
    changed = False
    for img in imgs:
        # Bump to v=9
        new_img = re.sub(r'\?v=\d+', '?v=9', img)
        if '?v=' not in img:
            new_img = img + '?v=9'
        new_imgs.append(new_img)
        if new_img != img:
            changed = True
    if changed:
        item['images'] = new_imgs
        updated += 1

print(f"Updated cache version for {updated} products")

with open('backend/search_index_v2.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False)

print("Saved search_index_v2.json")
