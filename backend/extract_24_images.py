import os, json
import fitz
from PIL import Image

JUNE_PDF = r"backend/uploads/Kohler_PriceBook (June'26).pdf"

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Find the 24 tiny images
target_codes = set()
for item in data.get('stored_items', []):
    if not isinstance(item, dict) or 'kohler' not in item.get('brand', '').lower(): continue
    sc = item.get('search_code')
    imgs = item.get('images', [])
    if not imgs: continue
    
    img_path = 'backend' + imgs[0].split('?')[0]
    if os.path.exists(img_path):
        try:
            with Image.open(img_path) as img:
                w, h = img.size
                if w < 100 and h < 100:
                    target_codes.add(sc)
        except:
            pass

print(f"Found {len(target_codes)} products to extract.")

# Group products by page
products_by_page = {}
for item in data.get('stored_items', []):
    if item.get('search_code') in target_codes:
        pg = item.get('page')
        if pg:
            if pg not in products_by_page: products_by_page[pg] = []
            products_by_page[pg].append(item)

print(f"Opening {JUNE_PDF}")
doc = fitz.open(JUNE_PDF)

extracted = 0

for pg_num, items in products_by_page.items():
    # PDF pages are 0-indexed, but usually stored_items 'page' is 1-indexed. Let's assume stored 'page' is 1-indexed.
    pdf_page_index = pg_num - 1
    if pdf_page_index < 0 or pdf_page_index >= len(doc): continue
    
    page = doc[pdf_page_index]
    blocks = page.get_text("dict")["blocks"]
    
    for item in items:
        sc = item.get('search_code')
        base = item.get('base_code') or sc
        
        found_y = None
        for b in blocks:
            if "lines" not in b: continue
            for l in b["lines"]:
                for s in l["spans"]:
                    text = s["text"].strip()
                    if text == base or text == sc:
                        found_y = s["bbox"][1] # y0
                        break
                if found_y: break
            if found_y: break
            
        if found_y is not None:
            # Create bounding box. Usually images are to the left of the text, and vertically around it.
            # Typical Kohler layout: left column is image. Text is to the right.
            # X from 30 to 180 (left column width). Y from found_y - 45 to found_y + 45.
            rect = fitz.Rect(30, found_y - 50, 200, found_y + 50)
            pix = page.get_pixmap(clip=rect, matrix=fitz.Matrix(2, 2)) # 2x resolution
            
            out_path = f"backend/static/images/Kohler/{sc}.png"
            pix.save(out_path)
            extracted += 1
            print(f"Extracted {sc} from page {pg_num}")
            
            # Update json to point to the new image, bump cache
            item['images'] = [f"/static/images/Kohler/{sc}.png?v=26"]

doc.close()

with open('backend/search_index_v2.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False)

print(f"Extraction complete! {extracted} images saved.")
