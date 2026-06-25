"""
CORRECT approach: Extract actual embedded images from Kohler PDF pages.
For each trim+valve product:
1. Find product code location on page (text bbox)
2. Find the image block that is positioned ABOVE and within the same column
3. Extract that specific embedded image (not a page crop)
4. Save cleanly with white background
"""

import fitz
import json
import os
import re
from PIL import Image
import io

PDF_PATH = r"backend/uploads/Kohler_PriceBook (June'26).pdf"
IMAGE_DIR = r"backend/static/images/Kohler"

# Load audit - these are the products whose images need fixing
with open('backend/trim_valve_audit.json') as f:
    audit = json.load(f)

# These were wrongly "fixed" - they now have page-crop images instead of product images
# Re-audit to find them
with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
items = data.get('stored_items', [])

with open('backend/trim_valve_products.json') as f:
    tv_data = json.load(f)
tv_codes = set(tv_data.get('codes', []))

code_to_item = {}
for item in items:
    if isinstance(item, dict):
        sc = item.get('search_code', '')
        if sc:
            code_to_item[sc] = item

doc = fitz.open(PDF_PATH)

def get_all_images_on_page(page):
    """Get all image xrefs with their bounding boxes on the page"""
    images = []
    for img_info in page.get_images(full=True):
        xref = img_info[0]
        rects = page.get_image_rects(xref)
        for rect in rects:
            images.append({'xref': xref, 'rect': rect})
    return images

def find_product_image(page, code, all_images):
    """
    Find the specific embedded image for a product code.
    The product image is the image bbox that is:
    - Above the product code text
    - In the same horizontal column
    - Reasonably sized (not tiny, not huge page-wide)
    """
    # Find code text position
    text_dict = page.get_text("dict")
    code_bbox = None
    base_code = re.sub(r'-(?:CP|AF|BV|BRD|RGD|BL)$', '', code)
    
    for block in text_dict["blocks"]:
        if block.get('type') != 0:
            continue
        for line in block.get('lines', []):
            lt = ' '.join(s['text'] for s in line.get('spans', []))
            if code in lt or (len(base_code) > 8 and base_code in lt):
                code_bbox = block['bbox']
                break
        if code_bbox:
            break
    
    if not code_bbox:
        return None, None
    
    cx0, cy0, cx1, cy1 = code_bbox
    code_mid_x = (cx0 + cx1) / 2
    
    # Page width for column size estimation
    page_w = page.rect.width
    col_width = page_w / 4  # typical column width
    
    # Find image that is:
    # 1. Above the code text (image bottom < code top, or image center < code center)
    # 2. Horizontally overlapping with the code
    # 3. Not too wide (not a full-page image)
    # 4. Has reasonable dimensions
    
    candidates = []
    for img in all_images:
        r = img['rect']
        img_cx = (r.x0 + r.x1) / 2
        img_cy = (r.y0 + r.y1) / 2
        img_w = r.x1 - r.x0
        img_h = r.y1 - r.y0
        
        # Must be above the text
        if r.y1 > cy0 + 10:
            continue
        
        # Must be in same horizontal column (within col_width of code center)
        if abs(img_cx - code_mid_x) > col_width:
            continue
        
        # Must not be too wide (full page background images excluded)
        if img_w > page_w * 0.7:
            continue
        
        # Must have reasonable size
        if img_w < 20 or img_h < 20:
            continue
        
        # Score: prefer closer to the code text, prefer larger
        dist = cy0 - r.y1  # distance from image bottom to text top
        area = img_w * img_h
        score = area / (dist + 1)
        
        candidates.append({'img': img, 'score': score, 'dist': dist, 'area': area, 'w': img_w, 'h': img_h})
    
    if not candidates:
        return None, code_bbox
    
    # Get best candidate (highest score = largest, closest)
    best = max(candidates, key=lambda x: x['score'])
    return best['img'], code_bbox

def extract_embedded_image(doc, img_info):
    """Extract the actual embedded image from PDF xref"""
    xref = img_info['xref']
    try:
        img_data = doc.extract_image(xref)
        if not img_data:
            return None
        img_bytes = img_data['image']
        pil_img = Image.open(io.BytesIO(img_bytes))
        # Convert to RGB with white background
        if pil_img.mode == 'CMYK':
            pil_img = pil_img.convert('RGB')
        elif pil_img.mode == 'RGBA':
            bg = Image.new('RGB', pil_img.size, (255,255,255))
            bg.paste(pil_img, mask=pil_img.split()[3])
            pil_img = bg
        elif pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')
        return pil_img
    except Exception as e:
        return None

# Get list of all trim+valve products to process
to_process = []
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
    if not is_tv:
        continue
    
    imgs = item.get('images', [])
    img_path = re.sub(r'\?v=\d+', '', imgs[0]) if imgs else ''
    img_filename = img_path.replace('/static/images/Kohler/', '').split('?')[0]
    if not img_filename:
        img_filename = f"{sc}.png"
    out_path = os.path.join(IMAGE_DIR, img_filename)
    page_num = item.get('page', 0)
    
    if page_num:
        to_process.append({
            'code': sc,
            'page': page_num,
            'out_path': out_path,
            'name': item.get('name', '')
        })

print(f"Products to fix: {len(to_process)}")

# Process by page (group to avoid re-rendering)
from collections import defaultdict
by_page = defaultdict(list)
for p in to_process:
    by_page[p['page']].append(p)

fixed = 0
failed = 0
failed_list = []

for page_num in sorted(by_page.keys()):
    page = doc[page_num - 1]
    all_images = get_all_images_on_page(page)
    
    for prod in by_page[page_num]:
        code = prod['code']
        out_path = prod['out_path']
        
        img_info, code_bbox = find_product_image(page, code, all_images)
        
        if img_info is None:
            failed += 1
            failed_list.append(f"p{page_num} {code}: no image found near code")
            continue
        
        pil_img = extract_embedded_image(doc, img_info)
        
        if pil_img is None:
            failed += 1
            failed_list.append(f"p{page_num} {code}: extract failed")
            continue
        
        w, h = pil_img.size
        if w < 50 or h < 50:
            failed += 1
            failed_list.append(f"p{page_num} {code}: too small {w}x{h}")
            continue
        
        # Add white background and save
        bg = Image.new('RGB', pil_img.size, (255, 255, 255))
        bg.paste(pil_img)
        bg.save(out_path, 'PNG')
        fixed += 1
        
    print(f"Page {page_num}: {len(by_page[page_num])} products done", flush=True)

doc.close()

print(f"\n=== RESULTS ===")
print(f"Fixed: {fixed}")
print(f"Failed: {failed}")
if failed_list:
    print("\nFailed:")
    for f in failed_list[:30]:
        print(f"  {f}")
