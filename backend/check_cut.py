import os, json
from PIL import Image

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

cut_products = []
for item in data.get('stored_items', []):
    if not isinstance(item, dict) or 'kohler' not in item.get('brand', '').lower(): continue
    
    sc = item.get('search_code')
    imgs = item.get('images', [])
    if not imgs: continue
    
    img_path = 'backend' + imgs[0].split('?')[0]
    if os.path.exists(img_path):
        try:
            with Image.open(img_path) as img:
                w, h = img.size
                if w < 120 or h < 120:
                    cut_products.append(f"{sc} ({w}x{h})")
        except Exception as e:
            pass

print(f'Total cut products remaining: {len(cut_products)}')
if cut_products:
    print('Examples:')
    for x in cut_products[:20]: print('  -', x)
