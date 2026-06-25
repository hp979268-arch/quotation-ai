"""
Bake the Windows App's dynamic image resolution logic directly into the static JSON file.
This ensures the Live Website serves the exact same high-quality fallback images 
that the Windows App backend automatically finds.
"""
import sys, os, json, copy
import re

sys.path.append(os.path.abspath('backend'))
import search_engine

# Force load to build the cache
search_engine.load_index(force=True)

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

changed = 0
for item in data.get('stored_items', []):
    if not isinstance(item, dict): continue
    
    # We only care about applying this to Kohler since Aquant is perfect
    if 'kohler' not in item.get('brand', '').lower():
        continue
        
    old_imgs = item.get('images', [])
    old_base_url = old_imgs[0].split('?')[0] if old_imgs else ""
    
    # We use search_engine's logic to find the best image on disk
    best_img = search_engine._best_item_image(item)
    
    if best_img and best_img != old_base_url:
        # Keep versioning if needed, but let's bump cache to v21 for changed ones
        item['images'] = [f"{best_img}?v=21"]
        changed += 1

print(f"Updated {changed} items with dynamically resolved images.")

with open('backend/search_index_v2.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False)
