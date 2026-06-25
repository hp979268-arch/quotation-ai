import json, os

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data.get('stored_items', [])

# Find Kohler items where any image has _v2
v2_products = []

for item in items:
    if not isinstance(item, dict):
        continue
    brand = item.get('brand', '')
    if 'kohler' not in brand.lower():
        continue

    imgs = item.get('images', [])
    for img in (imgs if isinstance(imgs, list) else [imgs]):
        if '_v2.' in str(img) or '_v2_' in str(img):
            v2_products.append(item)
            break

print(f'Total Kohler products with _v2 (trim+valve) image: {len(v2_products)}')
print()
for p in v2_products:
    print(f"  Code: {p.get('search_code','?')}")
    print(f"  Name: {p.get('name','?')[:80]}")
    print(f"  Images: {p.get('images','')}")
    print()
