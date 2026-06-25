"""
Fix Kohler trim+valve images by extracting the actual embedded images.
Correct Logic: Match the product code text block's Y-coordinate with
the image's Y-coordinate to find the image on the same row.
"""
import fitz
import json
import os
import re
from PIL import Image
import io

PDF_PATH = r"backend/uploads/Kohler_PriceBook (June'26).pdf"
IMAGE_DIR = r"backend/static/images/Kohler"

# Load audit to get the products we need to fix
# We will just re-extract everything that was marked as 'cropped' originally
with open('backend/trim_valve_audit.json') as f:
    audit = json.load(f)

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
items = data.get('stored_items', [])

with open('backend/trim_valve_products.json') as f:
    tv_data = json.load(f)
tv_codes = set(tv_data.get('codes', []))

doc = fitz.open(PDF_PATH)

def extract_proper_image(page, code, out_path):
    text_dict = page.get_text("dict")
    base_code = code.rsplit('-', 1)[0]
    code_bbox = None
    
    # Find text
    for block in text_dict["blocks"]:
        if block.get('type') != 0: continue
        for line in block.get('lines', []):
            lt = ' '.join(s['text'] for s in line.get('spans', []))
            if code in lt or (len(base_code) > 8 and base_code in lt):
                code_bbox = block['bbox']
                break
        if code_bbox: break
        
    if not code_bbox:
        return False, "Code text not found"
        
    code_cy = (code_bbox[1] + code_bbox[3]) / 2
    
    # Find all images
    all_images = []
    for img_info in page.get_images(full=True):
        xref = img_info[0]
        for rect in page.get_image_rects(xref):
            all_images.append({'xref': xref, 'rect': rect})
            
    # Find matching image by Y-coordinate
    best_img = None
    best_dist = float('inf')
    
    for img in all_images:
        r = img['rect']
        img_cy = (r.y0 + r.y1) / 2
        dist = abs(img_cy - code_cy)
        
        # Must be roughly on same row
        if dist < 60:
            if dist < best_dist:
                best_dist = dist
                best_img = img
                
    if not best_img:
        return False, "No matching image found on same row"
        
    # Extract
    try:
        img_data = doc.extract_image(best_img['xref'])
        pil_img = Image.open(io.BytesIO(img_data['image']))
        if pil_img.mode == 'CMYK': pil_img = pil_img.convert('RGB')
        elif pil_img.mode == 'RGBA':
            bg = Image.new('RGB', pil_img.size, (255,255,255))
            bg.paste(pil_img, mask=pil_img.split()[3])
            pil_img = bg
        elif pil_img.mode != 'RGB': pil_img = pil_img.convert('RGB')
        
        # Save
        pil_img.save(out_path)
        return True, f"Saved {pil_img.size}"
    except Exception as e:
        return False, f"Extract error: {e}"

# Get list to process
to_process = []
for item in items:
    if not isinstance(item, dict): continue
    sc = item.get('search_code', '')
    if 'kohler' in item.get('brand','').lower() and sc in tv_codes:
        imgs = item.get('images', [])
        img_path = re.sub(r'\?v=\d+', '', imgs[0]) if imgs else ''
        img_filename = img_path.replace('/static/images/Kohler/', '').split('?')[0]
        if not img_filename: img_filename = f"{sc}.png"
        out_path = os.path.join(IMAGE_DIR, img_filename)
        page_num = item.get('page', 0)
        
        if page_num:
            to_process.append((sc, page_num, out_path))

print(f"Processing {len(to_process)} products...")

fixed = 0
failed = 0
errors = []

from collections import defaultdict
by_page = defaultdict(list)
for p in to_process:
    by_page[p[1]].append(p)

for page_num in sorted(by_page.keys()):
    page = doc[page_num - 1]
    for code, _, out_path in by_page[page_num]:
        success, msg = extract_proper_image(page, code, out_path)
        if success:
            fixed += 1
        else:
            failed += 1
            errors.append(f"{code}: {msg}")

doc.close()

print(f"\nResults:")
print(f"Fixed: {fixed}")
print(f"Failed: {failed}")
if errors:
    print("Sample errors:")
    for e in errors[:10]: print(f"  {e}")
