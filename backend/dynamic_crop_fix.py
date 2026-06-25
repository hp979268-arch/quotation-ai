import os, json
import fitz
from PIL import Image

IMAGE_DIR = r"c:\Movies\quotation-ai\quotation-ai\backend\static\images\Kohler"
PDF_PATH = r"c:\Movies\quotation-ai\quotation-ai\backend\uploads\Kohler_PriceBook (June'26).pdf"
INDEX_PATH = r"c:\Movies\quotation-ai\quotation-ai\backend\search_index_v2.json"

# 1. Find all images that have width 396 or 270 (known bad crops) or are specific items
bad_images = set()
for f in os.listdir(IMAGE_DIR):
    if f.endswith('.png'):
        try:
            w, h = Image.open(os.path.join(IMAGE_DIR, f)).size
            if w == 396 or w == 270:
                bad_images.add(f)
        except:
            pass

# Ensure K-10712IN-AF is included
bad_images.add("K-10712IN-AF.png")
bad_images.add("K-10712IN AF.png")

print(f"Found {len(bad_images)} potentially bad images.")

with open(INDEX_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Find corresponding search items
items_to_fix = []
for item in data.get('stored_items', []):
    if item.get('brand', '').lower() == 'kohler':
        imgs = item.get('images', [])
        if not imgs: continue
        img_name = imgs[0].split('?')[0].split('/')[-1]
        
        # If the image name matches or the code is the specific one
        if img_name in bad_images or item.get('search_code') == 'K-10712IN-AF':
            if item.get('page'):
                items_to_fix.append(item)

print(f"Items to re-extract: {len(items_to_fix)}")

doc = fitz.open(PDF_PATH)
zoom = 3
fixed = 0

for item in items_to_fix:
    sc = item.get('search_code')
    pg_num = item.get('page')
    if not pg_num: continue
    
    page = doc[pg_num - 1]
    text_dict = page.get_text("dict")
    base = item.get('base_code') or sc
    code_bbox = None
    
    for block in text_dict["blocks"]:
        if block.get('type') != 0: continue
        for line in block.get('lines', []):
            lt = ' '.join(s['text'] for s in line.get('spans', []))
            if sc in lt or (len(base) > 6 and base in lt):
                code_bbox = block['bbox']
                break
        if code_bbox: break
        
    if not code_bbox:
        print(f"Code text not found for {sc}")
        continue
        
    code_cy = (code_bbox[1] + code_bbox[3]) / 2
    
    # Find image rects within 70px of code_cy
    all_rects = []
    for img_info in page.get_images(full=True):
        xref = img_info[0]
        for rect in page.get_image_rects(xref):
            img_cy = (rect.y0 + rect.y1) / 2
            if rect.x1 < 150 and abs(img_cy - code_cy) < 70:
                all_rects.append(rect)
                
    if not all_rects:
        print(f"No image rects found near {sc}")
        continue
        
    min_y = min(r.y0 for r in all_rects)
    max_y = max(r.y1 for r in all_rects)
    
    # DYNAMIC X BOUNDS!
    min_x = min(r.x0 for r in all_rects)
    max_x = max(r.x1 for r in all_rects)
    
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    full_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Crop using dynamic bounds with 5px padding
    crop_x0 = max(0, int((min_x - 5) * zoom))
    crop_y0 = max(0, int((min_y - 5) * zoom))
    crop_x1 = min(full_img.width, int((max_x + 5) * zoom))
    crop_y1 = min(full_img.height, int((max_y + 5) * zoom))
    
    if crop_y1 <= crop_y0 or crop_x1 <= crop_x0:
        print(f"Invalid crop bounds for {sc}")
        continue
        
    cropped = full_img.crop((crop_x0, crop_y0, crop_x1, crop_y1))
    
    # Add white background
    bg = Image.new('RGB', cropped.size, (255, 255, 255))
    bg.paste(cropped)
    
    out_path = os.path.join(IMAGE_DIR, f"{sc}.png")
    bg.save(out_path)
    
    item['images'] = [f"/static/images/Kohler/{sc}.png?v=30"]
    fixed += 1
    print(f"Fixed {sc} - new size: {bg.size}")

doc.close()

with open(INDEX_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False)

print(f"Successfully fixed {fixed} images.")
