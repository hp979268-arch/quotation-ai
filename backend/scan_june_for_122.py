import fitz
import json
import os
import re

# Load old JSON to get the 122 missing codes
with open("c:/Movies/quotation-ai/quotation-ai/backup_march_state_june23/search_index_v2.json", "r", encoding='utf-8') as f:
    old_data = json.load(f)

with open("c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json", "r", encoding='utf-8') as f:
    new_data = json.load(f)

old_codes = {i.get('search_code'): i for i in old_data.get('stored_items', []) if i.get('brand') == 'Kohler'}
new_codes = {i.get('search_code'): i for i in new_data.get('stored_items', []) if i.get('brand') == 'Kohler'}

missing_codes = set(old_codes.keys()) - set(new_codes.keys())
print(f"Scanning for {len(missing_codes)} missing codes in June PDF...")

PDF_PATH = r"c:\Movies\quotation-ai\quotation-ai\backend\uploads\Kohler_PriceBook (June'26).pdf"
OUT_DIR = r"c:\Movies\quotation-ai\quotation-ai\backend\uploads\june_test_images"
os.makedirs(OUT_DIR, exist_ok=True)

doc = fitz.open(PDF_PATH)
found = 0

# Naive scan for codes
for page_num in range(len(doc)):
    page = doc[page_num]
    text = page.get_text()
    
    for code in list(missing_codes):
        if code in text or code.replace('-', '') in text.replace('-', ''):
            # Extract basic image from this page for testing
            images = page.get_images(full=True)
            for i, img in enumerate(images[:1]): # just get first image for quick test
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    with open(os.path.join(OUT_DIR, f"{code}.{base_image['ext']}"), "wb") as f:
                        f.write(base_image["image"])
                    found += 1
                    missing_codes.remove(code)
                except:
                    pass

print(f"Found {found} out of 122 in the June PDF.")
if len(missing_codes) > 0:
    print("These codes were REMOVED from the June catalog (Not found):")
    print(list(missing_codes)[:10], "...")
