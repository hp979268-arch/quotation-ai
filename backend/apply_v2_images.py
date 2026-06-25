"""
Update search_index_v2.json to use the dual (_v2.png) images for the 40+ Trim+Valve products.
This will only change the images for products that have a _v2.png file available.
"""
import json
import os
import re

INDEX_PATH = 'backend/search_index_v2.json'
IMG_DIR = 'backend/static/images/Kohler'

# Find all _v2.png files
v2_files = [f for f in os.listdir(IMG_DIR) if f.endswith('_v2.png')]
v2_map = {f.replace('_v2.png', ''): f for f in v2_files}

with open(INDEX_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data.get('stored_items', [])

updated = 0
for item in items:
    if not isinstance(item, dict): continue
    if 'kohler' not in item.get('brand', '').lower(): continue
    
    sc = item.get('search_code', '')
    
    # If this product has a _v2 image available
    if sc in v2_map:
        v2_filename = v2_map[sc]
        v2_path = f'/static/images/Kohler/{v2_filename}?v=11'
        
        imgs = item.get('images', [])
        # If it doesn't already use the v2 image
        if not imgs or '_v2.png' not in imgs[0]:
            item['images'] = [v2_path]
            updated += 1
            print(f"Updated {sc} -> {v2_filename}")

print(f"\nTotal products updated to use dual images: {updated}")

with open(INDEX_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False)

print("Saved search_index_v2.json")
