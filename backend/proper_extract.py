import os, json
import fitz
from PIL import Image

codes = [
    'K-20740IN-A-NA', 'K-26343T-NA', 'K-882IN-NA', 'EX28093IN-8-AF', 'K-25758IN-4ND-AF',
    'K-25757IN-4ND-RGD', 'K-23472IN-4ND-BRD', 'K-72312IN-4ND-BRD', 'K-23486IN-4ND-BRD',
    'K-5683IN-4ND-BRD', 'K-27488IN-4ND-AF', 'K-27490IN-AF', 'K-27493IN-AF', 'K-27499IN-4FS-AF',
    'K-29959IN-AF', 'K-30319IN-NA', 'K-34098IN-BRD', 'K-34099IN-BRD', 'K-73040IN-CL-BL', 'K-99035T-ZZ-RGD'
]

JUNE_PDF = r"backend/uploads/Kohler_PriceBook (June'26).pdf"

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Build lookup
products = {}
for item in data.get('stored_items', []):
    sc = item.get('search_code')
    if sc in codes:
        products[sc] = item

doc = fitz.open(JUNE_PDF)
zoom = 3
extracted = 0

for sc in codes:
    item = products.get(sc)
    if not item: continue
    
    pg_num = item.get('page')
    if not pg_num: continue
    page = doc[pg_num - 1]
    
    # 1. Find y of the text
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
    
    # 2. Find image rects within 70px of code_cy
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
    
    # Render page
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    full_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Crop using the exact same logic as clean_crop_images.py
    crop_x0 = int(35 * zoom)
    crop_x1 = int(125 * zoom)
    crop_y0 = int((min_y - 5) * zoom)
    crop_y1 = int((max_y + 5) * zoom)
    
    crop_y0 = max(0, crop_y0)
    crop_y1 = min(full_img.height, crop_y1)
    
    if crop_y1 <= crop_y0:
        continue
        
    cropped = full_img.crop((crop_x0, crop_y0, crop_x1, crop_y1))
    
    # Add white background
    bg = Image.new('RGB', cropped.size, (255, 255, 255))
    bg.paste(cropped)
    
    out_path = f"backend/static/images/Kohler/{sc}.png"
    bg.save(out_path)
    extracted += 1
    print(f"Saved proper clean crop for {sc}")
    
    item['images'] = [f"/static/images/Kohler/{sc}.png?v=28"]

doc.close()

with open('backend/search_index_v2.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False)

print(f"Successfully extracted {extracted} proper images.")
