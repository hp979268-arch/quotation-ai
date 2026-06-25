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

def rect_distance(r1, r2):
    # Calculate shortest distance between two rects
    dx = max(0, max(r1.x0 - r2.x1, r2.x0 - r1.x1))
    dy = max(0, max(r1.y0 - r2.y1, r2.y0 - r1.y1))
    return (dx**2 + dy**2)**0.5

extracted = 0

for sc in codes:
    item = products.get(sc)
    if not item: continue
    
    pg_num = item.get('page')
    if not pg_num: continue
    pdf_page_index = pg_num - 1
    page = doc[pdf_page_index]
    
    # 1. Find y of the text
    blocks = page.get_text("dict")["blocks"]
    base = item.get('base_code') or sc
    found_y = None
    
    for b in blocks:
        if "lines" not in b: continue
        for l in b["lines"]:
            for s in l["spans"]:
                text = s["text"].strip()
                if text == base or text == sc:
                    found_y = s["bbox"][1]
                    break
            if found_y: break
        if found_y: break
        
    if found_y is None:
        print(f"Text not found for {sc}")
        continue
        
    # 2. Collect all image rects on the page
    img_rects = []
    for img_info in page.get_images(full=True):
        xref = img_info[0]
        rects = page.get_image_rects(xref)
        for r in rects:
            # Typical Kohler layout has images on the left side (x < 250)
            if r.x0 < 250:
                img_rects.append(r)
                
    if not img_rects:
        continue
        
    # 3. Find primary rect closest to found_y
    primary_rect = min(img_rects, key=lambda r: min(abs(r.y0 - found_y), abs(r.y1 - found_y)))
    
    # 4. Group adjacent rects
    cluster = [primary_rect]
    added = True
    while added:
        added = False
        for r in img_rects:
            if r in cluster: continue
            # If r is within 25 pixels of ANY rect in the cluster, add it
            # 25px gap handles small separations in split images
            for c in cluster:
                if rect_distance(r, c) < 25:
                    cluster.append(r)
                    added = True
                    break
                    
    # 5. Create final bounding box from cluster
    final_rect = fitz.Rect(cluster[0])
    for r in cluster[1:]:
        final_rect.include_rect(r)
        
    # Pad by 2 pixels just to avoid cutting the edges
    final_rect = final_rect + (-2, -2, 2, 2)
    
    # Render and save
    pix = page.get_pixmap(clip=final_rect, matrix=fitz.Matrix(2, 2))
    out_path = f"backend/static/images/Kohler/{sc}.png"
    pix.save(out_path)
    extracted += 1
    print(f"Extracted precise image for {sc}")
    
    item['images'] = [f"/static/images/Kohler/{sc}.png?v=27"]

doc.close()

with open('backend/search_index_v2.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False)

print(f"Successfully extracted {extracted} precise images.")
