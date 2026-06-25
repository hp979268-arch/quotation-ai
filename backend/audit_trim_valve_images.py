import sys, json, os, re
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
items = data.get('stored_items', [])

with open('backend/trim_valve_products.json', 'r', encoding='utf-8') as f:
    tv_data = json.load(f)
tv_codes = set(tv_data.get('codes', []))

IMAGE_BASE = 'backend/static/images'
missing, cropped, ok, no_img = [], [], [], []

for item in items:
    if not isinstance(item, dict):
        continue
    if 'kohler' not in item.get('brand', '').lower():
        continue
    sc = item.get('search_code', '')
    cat = item.get('category', '').lower()
    is_tv = (
        sc in tv_codes or
        'in-wall' in cat or 'concealed' in cat or
        '4nd' in sc.lower() or '4fs' in sc.lower() or '4fp' in sc.lower()
    )
    if not is_tv:
        continue
    imgs = item.get('images', [])
    if not imgs:
        no_img.append({'code': sc})
        continue
    img_path = re.sub(r'\?v=\d+', '', imgs[0])
    local_path = 'backend/static/images/' + img_path.replace('/static/images/', '')
    if not os.path.exists(local_path):
        missing.append({'code': sc, 'path': img_path})
        continue
    try:
        with Image.open(local_path) as img:
            w, h = img.size
        if w < 200 or h < 150:
            cropped.append({
                'code': sc,
                'path': img_path,
                'size': f'{w}x{h}',
                'page': item.get('page', 0),
                'name': item.get('name', '')[:60]
            })
        else:
            ok.append(sc)
    except Exception as e:
        missing.append({'code': sc, 'path': img_path, 'error': str(e)})

print(f'OK: {len(ok)}, Missing: {len(missing)}, Cropped: {len(cropped)}, NoImg: {len(no_img)}')
print('\nCROPPED IMAGES:')
for p in cropped:
    print(f'  {p["code"]} [{p["size"]}] page={p["page"]} - {p["name"]}')
print(f'\nMISSING FILES ({len(missing)}):')
for p in missing[:30]:
    print(f'  {p["code"]}: {p.get("path", "")}')

with open('backend/trim_valve_audit.json', 'w') as f:
    json.dump({'missing': missing, 'cropped': cropped, 'no_img': no_img}, f, indent=2)
print(f'\nSaved to backend/trim_valve_audit.json')
