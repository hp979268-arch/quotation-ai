"""
Rebuild gallery with UPDATED images (after fix) using direct file paths
"""

import json
import os
import re
from collections import defaultdict

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
items = data.get('stored_items', [])

with open('backend/trim_valve_products.json', 'r', encoding='utf-8') as f:
    tv_data = json.load(f)
tv_codes = set(tv_data.get('codes', []))

gallery_products = []
seen = set()

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
    if not is_tv or sc in seen:
        continue
    seen.add(sc)

    imgs = item.get('images', [])
    img_path = re.sub(r'\?v=\d+', '', imgs[0]) if imgs else ''
    local_path = 'backend/static/images/Kohler/' + img_path.replace('/static/images/Kohler/', '') if img_path else ''
    file_exists = os.path.exists(local_path)

    gallery_products.append({
        'code': sc,
        'name': item.get('name', '')[:70],
        'category': item.get('category', ''),
        'price': item.get('price', ''),
        'image_url': 'file:///c:/Movies/quotation-ai/quotation-ai/' + local_path.replace('\\','/') if file_exists else '',
        'img_path': img_path,
        'exists': file_exists,
        'in_tv_list': sc in tv_codes,
    })

gallery_products.sort(key=lambda x: x['code'])

base_groups = defaultdict(list)
for p in gallery_products:
    base = re.sub(r'-(?:CP|AF|BV|BRD|RGD|BL|NA|0|ND)$', '', p['code'])
    base_groups[base].append(p)

total = len(gallery_products)
with_img = len([p for p in gallery_products if p['exists']])
without_img = total - with_img

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Kohler Trim+Valve - Fixed Images Gallery</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; margin:0; }}
  h1 {{ color: #38bdf8; text-align: center; margin-bottom: 5px; }}
  .subtitle {{ text-align:center; color:#94a3b8; margin-bottom:20px; font-size:14px; }}
  .summary {{ background: #1e293b; padding: 15px 25px; border-radius: 10px; margin-bottom: 25px; text-align: center; display:flex; justify-content:center; gap:30px; flex-wrap:wrap; }}
  .summary span {{ font-size: 16px; font-weight: bold; }}
  .ok {{ color: #4ade80; }}
  .bad {{ color: #f87171; }}
  .tv {{ color: #fbbf24; }}
  .filters {{ text-align: center; margin-bottom: 20px; }}
  .search-box {{ width: 320px; padding: 10px; border-radius: 8px; border: 1px solid #38bdf8; background: #1e293b; color: white; font-size: 15px; margin-bottom: 10px; }}
  .filters button {{ background: #0ea5e9; color: white; border: none; padding: 9px 20px; margin: 4px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight:bold; }}
  .filters button:hover {{ background: #0284c7; }}
  .group {{ margin-bottom: 25px; background: #1e293b; border-radius: 12px; padding: 15px 18px; }}
  .group-title {{ color: #fff; background: #0ea5e9; padding: 4px 14px; border-radius: 6px; font-weight: bold; font-size:13px; margin-bottom: 12px; display: inline-block; }}
  .products {{ display: flex; flex-wrap: wrap; gap: 12px; }}
  .card {{ background: #0f172a; border-radius: 10px; padding: 10px; width: 200px; text-align: center; border: 2px solid #22d3ee; transition: transform 0.15s; }}
  .card:hover {{ transform: scale(1.04); }}
  .card.no-img {{ border-color: #f87171; }}
  .card img {{ width: 180px; height: 150px; object-fit: contain; background: white; border-radius: 6px; }}
  .no-img-box {{ width: 180px; height: 150px; background: #1e293b; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: #f87171; font-size: 13px; }}
  .code {{ font-size: 11px; color: #7dd3fc; margin-top: 7px; word-break: break-all; font-weight:bold; }}
  .cat {{ font-size: 10px; color: #64748b; margin-top: 3px; }}
  .price {{ font-size: 12px; color: #4ade80; margin-top: 4px; font-weight: bold; }}
</style>
</head>
<body>
<h1>Kohler Trim+Valve — Fixed Image Gallery</h1>
<p class="subtitle">All images re-extracted from PDF at full resolution</p>
<div class="summary">
  <span>Total: <b style="color:#e2e8f0">{total}</b></span>
  <span class="ok">With Image: {with_img}</span>
  <span class="bad">Missing: {without_img}</span>
</div>
<div class="filters">
  <input type="text" class="search-box" id="searchBox" placeholder="Search by code e.g. K-38893..." onkeyup="filterCards()">
  <br>
  <button onclick="showAll()">All</button>
  <button onclick="showNoImage()" style="background:#ef4444">Missing Image</button>
</div>
<div id="gallery">
'''

for group_base, prods in sorted(base_groups.items()):
    html += f'<div class="group">\n<span class="group-title">{group_base}</span>\n<div class="products">\n'
    for p in prods:
        card_cls = 'card' if p['exists'] else 'card no-img'
        has_img_attr = 'true' if p['exists'] else 'false'
        html += f'<div class="{card_cls}" data-code="{p["code"].lower()}" data-has-img="{has_img_attr}">\n'
        if p['exists'] and p['image_url']:
            html += f'  <img src="{p["image_url"]}" alt="{p["code"]}" loading="lazy" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\';">\n'
            html += f'  <div class="no-img-box" style="display:none">Load Error</div>\n'
        else:
            html += f'  <div class="no-img-box">No Image</div>\n'
        try:
            price_str = f'MRP: {float(p["price"]):,.0f}' if p['price'] else ''
        except:
            price_str = ''
        html += f'  <div class="code">{p["code"]}</div>\n'
        html += f'  <div class="cat">{p["category"][:40]}</div>\n'
        html += f'  <div class="price">{price_str}</div>\n'
        html += '</div>\n'
    html += '</div>\n</div>\n'

html += '''</div>
<script>
function filterCards(){
  const q=document.getElementById('searchBox').value.toLowerCase();
  document.querySelectorAll('.card').forEach(c=>{
    c.style.display=c.getAttribute('data-code').includes(q)?'':'none';
  });
  document.querySelectorAll('.group').forEach(g=>{
    const vis=[...g.querySelectorAll('.card')].some(c=>c.style.display!=='none');
    g.style.display=vis?'':'none';
  });
}
function showAll(){document.querySelectorAll('.card,.group').forEach(c=>c.style.display='');}
function showNoImage(){
  document.querySelectorAll('.card').forEach(c=>{
    c.style.display=c.getAttribute('data-has-img')==='false'?'':'none';
  });
  document.querySelectorAll('.group').forEach(g=>{
    const vis=[...g.querySelectorAll('.card')].some(c=>c.style.display!=='none');
    g.style.display=vis?'':'none';
  });
}
</script>
</body></html>'''

out = 'backend/trim_valve_gallery.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Gallery saved: {out}")
print(f"Total: {total}, With image: {with_img}, Missing: {without_img}")
