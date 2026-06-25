import json
import os
import urllib.parse
import re

def main():
    index_path = 'c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json'
    image_dir = 'c:/Movies/quotation-ai/quotation-ai/backend/static/images/Kohler'
    
    with open(index_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    kohler_items = [i for i in data.get('stored_items', []) if i.get('brand', '').lower() == 'kohler']
    
    # Build sets of valid identifiers
    valid_codes = set()
    referenced_filenames = set()
    
    for item in kohler_items:
        sc = str(item.get('search_code', '')).strip().lower()
        if sc:
            valid_codes.add(sc)
            
        bc = str(item.get('base_code', '')).strip().lower()
        if bc:
            valid_codes.add(bc)
            
        for img_url in item.get('images', []):
            filename = urllib.parse.urlparse(img_url).path.split('/')[-1].lower()
            if filename:
                referenced_filenames.add(filename)
                
    # Check all files in directory
    existing_files = [f for f in os.listdir(image_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    orphans = []
    
    for f in existing_files:
        f_lower = f.lower()
        
        # 1. Direct match with a referenced URL filename
        if f_lower in referenced_filenames:
            continue
            
        # 2. Extract base name without extension
        # e.g., "k-1234.png" -> "k-1234", "k-1234_v2.png" -> "k-1234"
        base_name = re.sub(r'(_v[0-9]+)?\.(png|jpg|jpeg)$', '', f_lower)
        
        # 3. Match against search_code or base_code
        if base_name in valid_codes:
            continue
            
        # 4. Sometimes they have spaces or hyphens replaced, let's be generous
        base_name_clean = base_name.replace('-', '').replace(' ', '')
        if any(c.replace('-', '').replace(' ', '') == base_name_clean for c in valid_codes):
            continue
            
        orphans.append(f)
        
    orphans.sort()
    
    report_path = 'c:/Movies/quotation-ai/quotation-ai/backend/orphan_images_report.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# Kohler Orphan Images Report\n\n")
        f.write(f"- Total Images in Folder: {len(existing_files)}\n")
        f.write(f"- Images WITHOUT a Matching Product: {len(orphans)}\n\n")
        f.write("## Orphan Images List\n\n")
        for orphan in orphans:
            f.write(f"- `{orphan}`\n")
            
    print(f"Total files: {len(existing_files)}")
    print(f"Orphan images: {len(orphans)}")

if __name__ == '__main__':
    main()
