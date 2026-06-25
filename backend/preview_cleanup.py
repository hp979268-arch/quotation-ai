import sys, os, json
sys.path.append(os.path.abspath('backend'))
import search_engine
search_engine.load_index(force=True)

target_renames = []

for item in search_engine.stored_items:
    if 'kohler' not in item.get('brand', '').lower(): continue
    
    sc = item.get('search_code')
    if not sc: continue
    
    best_img = search_engine._best_item_image(item)
    if not best_img: continue
    
    # Standard name
    standard_name = f"{sc}.png"
    standard_path = f"/static/images/Kohler/{standard_name}"
    
    local_best_path = 'backend' + best_img
    local_std_path = 'backend' + standard_path
    
    if best_img != standard_path and os.path.exists(local_best_path):
        target_renames.append((local_best_path, local_std_path))
        
print(f'Need to overwrite {len(target_renames)} standard images with best images.')
