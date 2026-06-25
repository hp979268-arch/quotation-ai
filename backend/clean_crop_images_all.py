"""
Fix 'cut' images by rendering the page at high DPI and cropping the exact image area.
This handles PDFs where images are split into multiple embedded objects.
Process ALL trim+valve products (do not skip any).
"""
import fitz
import json
import os
import re
from PIL import Image
import io

PDF_PATH = r"backend/uploads/Kohler_PriceBook (June'26).pdf"
IMAGE_DIR = r"backend/static/images/Kohler"

# Load search index
with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
items = data.get('stored_items', [])

# Get list of products to process (trim+valve ones)
with open('backend/trim_valve_products.json') as f:
    tv_data = json.load(f)
tv_codes = set(tv_data.get('codes', []))

doc = fitz.open(PDF_PATH)
zoom = 3

def get_clean_crop(page, code, out_path):
    text_dict = page.get_text("dict")
    base_code = code.rsplit('-', 1)[0]
    code_bbox = None
    
    # Find text to get Y anchor
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
    
    # Find all image rects to determine the bounding box
    all_rects = []
    for img_info in page.get_images(full=True):
        xref = img_info[0]
        for rect in page.get_image_rects(xref):
            # Only consider images in the left column (x < 150)
            # and roughly on the same row as the text
            img_cy = (rect.y0 + rect.y1) / 2
            if rect.x1 < 150 and abs(img_cy - code_cy) < 70:
                all_rects.append(rect)
                
    if not all_rects:
        return False, "No images found near code"
        
    # Calculate bounding box encompassing all relevant image parts
    min_y = min(r.y0 for r in all_rects)
    max_y = max(r.y1 for r in all_rects)
    
    # Render page
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    full_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Crop exactly the image column and the Y range
    # Column width is roughly 40 to 120 in PDF points
    crop_x0 = int(35 * zoom)
    crop_x1 = int(125 * zoom)
    crop_y0 = int((min_y - 5) * zoom)
    crop_y1 = int((max_y + 5) * zoom)
    
    # Ensure valid bounds
    crop_y0 = max(0, crop_y0)
    crop_y1 = min(full_img.height, crop_y1)
    
    if crop_y1 <= crop_y0:
        return False, "Invalid crop bounds"
        
    cropped = full_img.crop((crop_x0, crop_y0, crop_x1, crop_y1))
    
    # Add white background
    bg = Image.new('RGB', cropped.size, (255, 255, 255))
    bg.paste(cropped)
    bg.save(out_path)
    return True, f"Saved clean crop {cropped.size}"


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

from collections import defaultdict
by_page = defaultdict(list)
for p in to_process:
    by_page[p[1]].append(p)

for page_num in sorted(by_page.keys()):
    page = doc[page_num - 1]
    for code, _, out_path in by_page[page_num]:
        success, msg = get_clean_crop(page, code, out_path)
        if success:
            fixed += 1
        else:
            failed += 1

doc.close()
print(f"\nFixed: {fixed}, Failed: {failed}")
