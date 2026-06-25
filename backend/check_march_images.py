"""
Check March PDF for better quality images of trim+valve products.
Compare image sizes between March and June PDFs.
"""

import fitz
import json
import re

MARCH_PDF = r"backend/uploads/Kohler_PriceBook (June'26).pdf"
JUNE_PDF = r"backend/uploads/Kohler_PriceBook (June'26).pdf"

# Load our trim+valve product list
with open('backend/trim_valve_products.json') as f:
    tv_data = json.load(f)
tv_codes = set(tv_data.get('codes', []))

# Load search index for page numbers
with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
items = data.get('stored_items', [])

# Get products we need to fix (those with small images in June)
code_to_item = {}
for item in items:
    if isinstance(item, dict):
        sc = item.get('search_code', '')
        if sc:
            code_to_item[sc] = item

march_doc = fitz.open(MARCH_PDF)
june_doc = fitz.open(JUNE_PDF)

print(f"March PDF pages: {len(march_doc)}")
print(f"June PDF pages: {len(june_doc)}")

# Search for specific trim+valve products in March PDF
# Sample codes to test
test_codes = ['K-73159IN-7-CP', 'K-38893IN-4ND-CP', 'K-25757IN-4ND-CP', 
               'K-72337IN-4ND-CP', 'K-26347IN-9-AF', 'K-38886IN-4ND-AF']

print("\n=== Searching in MARCH PDF ===")
for code in test_codes:
    found = False
    for pn in range(len(march_doc)):
        page = march_doc[pn]
        text = page.get_text()
        base = code.rsplit('-', 1)[0]  # Remove finish suffix
        if code in text or (base in text and len(base) > 8):
            # Count images on this page
            images = page.get_images(full=True)
            # Get image sizes
            sizes = []
            for img in images:
                xref = img[0]
                rects = page.get_image_rects(xref)
                for rect in rects:
                    w = int(rect.x1 - rect.x0)
                    h = int(rect.y1 - rect.y0)
                    sizes.append(f"{w}x{h}")
            
            # Also check raw embedded image size (actual pixels)
            raw_sizes = []
            for img in images[:5]:
                xref = img[0]
                try:
                    img_data = march_doc.extract_image(xref)
                    raw_sizes.append(f"{img_data['width']}x{img_data['height']}")
                except:
                    pass
            
            print(f"  {code}: FOUND on March page {pn+1}")
            print(f"    Page image count: {len(images)}")
            print(f"    PDF display sizes: {sizes[:5]}")
            print(f"    Raw pixel sizes: {raw_sizes}")
            found = True
            break
    if not found:
        print(f"  {code}: NOT FOUND in March PDF")

march_doc.close()
june_doc.close()
