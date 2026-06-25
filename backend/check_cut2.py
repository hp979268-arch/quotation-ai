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
                if w < 100 and h < 100:  # really tiny
                    cut_products.append(f"{sc} ({w}x{h})")
        except:
            pass

print(f'Products with BOTH width & height < 100px: {len(cut_products)}')
if cut_products:
    for x in cut_products[:15]: print('  -', x)
