import sys, os, json, shutil

sys.path.append(os.path.abspath('backend'))
import search_engine
search_engine.load_index(force=True)

IMAGE_DIR = 'backend/static/images/Kohler'
target_renames = []

# Gather renames
for item in search_engine.stored_items:
    if 'kohler' not in item.get('brand', '').lower(): continue
    
    sc = item.get('search_code')
    if not sc: continue
    
    best_img = search_engine._best_item_image(item)
    if not best_img: continue
    
    standard_name = f"{sc}.png"
    standard_path = f"/static/images/Kohler/{standard_name}"
    
    local_best_path = 'backend' + best_img
    local_std_path = 'backend' + standard_path
    
    if best_img != standard_path and os.path.exists(local_best_path):
        target_renames.append((local_best_path, local_std_path, sc))

print(f'Starting replacement of {len(target_renames)} images...')

renamed_count = 0
deleted_count = 0

for best_path, std_path, sc in target_renames:
    # We must be careful. We want std_path to have the contents of best_path.
    # If std_path exists, we overwrite it.
    if os.path.exists(best_path):
        # Use shutil.copy2 to preserve metadata, just in case
        shutil.copy2(best_path, std_path)
        renamed_count += 1
        
        # Now clean up other junk files for this product
        # e.g. space-separated, _v2, _v3, etc.
        for f in os.listdir(IMAGE_DIR):
            # Check if this file belongs to the same base search code
            if f.startswith(sc) and f != f"{sc}.png":
                # Only delete if it's an alternate version (has space, _v, etc)
                # We need to be careful not to delete variants like K-123-A if sc is K-123
                if f.startswith(sc + ' ') or f.startswith(sc + '_v') or f.startswith(sc + '('):
                    junk_path = os.path.join(IMAGE_DIR, f)
                    try:
                        os.remove(junk_path)
                        deleted_count += 1
                    except:
                        pass

print(f'Successfully copied {renamed_count} high-res images to standard names.')
print(f'Cleaned up {deleted_count} duplicate/junk files.')

# Now rewrite JSON
with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data.get('stored_items', []):
    if isinstance(item, dict) and 'kohler' in item.get('brand', '').lower():
        sc = item.get('search_code')
        item['images'] = [f"/static/images/Kohler/{sc}.png?v=25"]

with open('backend/search_index_v2.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False)

print('Updated search_index_v2.json to point to standard paths (v=25).')
