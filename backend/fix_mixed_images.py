"""
Fix 'mixed' images where adjacent products were merged together.
Instead of a wide 70px window, we find the closest image part,
then only include other parts that are immediately adjacent/overlapping
to the main part.
"""
import fitz
import json
import os
import re
from PIL import Image
import io

PDF_PATH = r"backend/uploads/Kohler_PriceBook (June'26).pdf"
IMAGE_DIR = r"backend/static/images/Kohler"

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
items = data.get('stored_items', [])

with open('backend/trim_valve_products.json') as f:
    tv_data = json.load(f)
tv_codes = set(tv_data.get('codes', []))

doc = fitz.open(PDF_PATH)
zoom = 3

def get_precise_crop(page, code, out_path):
    text_dict = page.get_text("dict")
    base_code = code.rsplit('-', 1)[0]
    code_bbox = None
    
    # Find text Y anchor
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
    
    # Find all images in the left column
    left_images = []
    for img_info in page.get_images(full=True):
        xref = img_info[0]
        for rect in page.get_image_rects(xref):
            if rect.x1 < 160:  # In image column
                left_images.append(rect)
                
    if not left_images:
        return False, "No images found in column"
        
    # Find the single closest image part
    left_images.sort(key=lambda r: abs(((r.y0+r.y1)/2) - code_cy))
    primary_rect = left_images[0]
    
    # If the closest image is still too far away, it might be a missing image
    if abs(((primary_rect.y0+primary_rect.y1)/2) - code_cy) > 60:
        return False, "Closest image is too far"
        
    # Now gather all image parts that are vertically contiguous/overlapping with the primary rect
    # Expand the primary rect bounds slightly to catch adjacent parts
    min_y = primary_rect.y0
    max_y = primary_rect.y1
    
    # Grow bounds until no more parts touch it
    added = True
    while added:
        added = False
        for rect in left_images:
            if rect == primary_rect: continue
            
            # Check if this rect is close to our current bounds (e.g. within 5 pixels)
            if rect.y0 <= max_y + 5 and rect.y1 >= min_y - 5:
                # Include it if it extends the bounds
                if rect.y0 < min_y or rect.y1 > max_y:
                    min_y = min(min_y, rect.y0)
                    max_y = max(max_y, rect.y1)
                    added = True
    
    # Now we have precise min_y and max_y for just this product's image cluster
    
    # Render page
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    full_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Crop
    crop_x0 = int(35 * zoom)
    crop_x1 = int(125 * zoom)
    crop_y0 = int((min_y - 2) * zoom)
    crop_y1 = int((max_y + 2) * zoom)
    
    crop_y0 = max(0, crop_y0)
    crop_y1 = min(full_img.height, crop_y1)
    
    if crop_y1 <= crop_y0:
        return False, "Invalid crop bounds"
        
    cropped = full_img.crop((crop_x0, crop_y0, crop_x1, crop_y1))
    
    # White background
    bg = Image.new('RGB', cropped.size, (255, 255, 255))
    bg.paste(cropped)
    bg.save(out_path)
    return True, "OK"

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

print(f"Fixing {len(to_process)} products...")

fixed = 0
failed = 0

from collections import defaultdict
by_page = defaultdict(list)
for p in to_process:
    by_page[p[1]].append(p)

for page_num in sorted(by_page.keys()):
    page = doc[page_num - 1]
    for code, _, out_path in by_page[page_num]:
        success, msg = get_precise_crop(page, code, out_path)
        if success:
            fixed += 1
        else:
            failed += 1

doc.close()
print(f"Fixed: {fixed}, Failed: {failed}")
