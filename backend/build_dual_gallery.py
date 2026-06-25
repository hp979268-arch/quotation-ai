"""
Build an HTML gallery of ONLY the 40 dual (_v2.png) trim+valve products
"""
import json
import os
import re

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data.get('stored_items', [])

gallery_products = []

for item in items:
    if not isinstance(item, dict):
        continue
    sc = item.get('search_code', '')
    imgs = item.get('images', [])
    
    # We want only the ones that have a _v2.png image
    if imgs and '_v2.png' in imgs[0]:
        img_path = re.sub(r'\?v=\d+', '', imgs[0])
        local_path = 'backend/static/images/Kohler/' + img_path.replace('/static/images/Kohler/', '')
        file_exists = os.path.exists(local_path)
        
        gallery_products.append({
            'code': sc,
            'name': item.get('name', '')[:70],
            'image_url': 'file:///c:/Movies/quotation-ai/quotation-ai/' + local_path.replace('\\','/') if file_exists else '',
            'exists': file_exists
        })

# Sort alphabetically
gallery_products.sort(key=lambda x: x['code'])

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Dual Trim+Valve Images (_v2)</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
  h1 {{ color: #38bdf8; text-align: center; }}
  .summary {{ text-align: center; margin-bottom: 30px; font-size: 18px; }}
  .products {{ display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; }}
  .card {{ background: #1e293b; border-radius: 10px; padding: 15px; width: 220px; text-align: center; border: 2px solid #38bdf8; }}
  .card img {{ width: 200px; height: 200px; object-fit: contain; background: white; border-radius: 6px; }}
  .code {{ font-size: 14px; color: #7dd3fc; margin-top: 10px; font-weight: bold; word-break: break-all; }}
  .name {{ font-size: 11px; color: #94a3b8; margin-top: 5px; }}
</style>
</head>
<body>
<h1>Dual Trim+Valve Images</h1>
<div class="summary">Total <strong>{len(gallery_products)}</strong> dual images mapped.</div>
<div class="products">
'''

for p in gallery_products:
    html += '<div class="card">\n'
    if p['exists'] and p['image_url']:
        html += f'  <img src="{p["image_url"]}" alt="{p["code"]}">\n'
    else:
        html += f'  <div style="height:200px; line-height:200px; color:#f87171;">Image Missing</div>\n'
    html += f'  <div class="code">{p["code"]}</div>\n'
    html += f'  <div class="name">{p["name"]}</div>\n'
    html += '</div>\n'

html += '</div></body></html>'

out = 'backend/dual_images_gallery.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Gallery saved to {out} with {len(gallery_products)} products")
