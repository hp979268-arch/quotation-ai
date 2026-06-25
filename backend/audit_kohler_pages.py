"""
Audit Kohler Images from Page 99 to 136.
Reports any missing, broken, very small, or distorted images.
"""
import json
import os
from PIL import Image

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data.get('stored_items', [])

target_products = []
for item in items:
    if not isinstance(item, dict): continue
    if 'kohler' in item.get('brand', '').lower():
        page = item.get('page', 0)
        if 99 <= page <= 136:
            target_products.append(item)

print(f"Total Kohler Products between Page 99 and 136: {len(target_products)}")

missing_images = []
not_found_placeholder = []
small_images = []
extreme_aspect = []

for item in target_products:
    sc = item.get('search_code')
    imgs = item.get('images', [])
    
    if not imgs:
        missing_images.append(sc)
        continue
        
    img_url = imgs[0].split('?')[0]
    
    if 'Image_Not_Found' in img_url:
        not_found_placeholder.append(sc)
        continue
        
    local_path = 'backend' + img_url
    if not os.path.isfile(local_path):
        missing_images.append(f"{sc} (File {local_path} not found)")
        continue
        
    try:
        with Image.open(local_path) as img:
            w, h = img.size
            
            if w < 120 or h < 120:
                small_images.append(f"{sc} ({w}x{h})")
                
            if h > 0 and w > 0:
                ar = w / h
                if ar > 3 or ar < 0.33:
                    extreme_aspect.append(f"{sc} ({w}x{h}, AR: {ar:.2f})")
    except Exception as e:
        missing_images.append(f"{sc} (Corrupt file)")

print(f"\nReport for Pages 99 to 136:")
print(f"Total Products Checked: {len(target_products)}")
print(f"1. Missing / Broken Files: {len(missing_images)}")
print(f"2. Image Not Found Placeholders: {len(not_found_placeholder)}")
print(f"3. Very Small Images (<120px): {len(small_images)}")
print(f"4. Extremely Distorted/Cut Aspect Ratios: {len(extreme_aspect)}")

if missing_images:
    print("\nMissing/Broken Samples:")
    for x in missing_images[:10]: print("  -", x)

if not_found_placeholder:
    print("\nPlaceholder Samples:")
    for x in not_found_placeholder[:10]: print("  -", x)

if small_images:
    print("\nSmall/Cut Image Samples (Often means only a piece was extracted):")
    for x in small_images[:10]: print("  -", x)

if extreme_aspect:
    print("\nDistorted Aspect Ratio Samples:")
    for x in extreme_aspect[:10]: print("  -", x)
