import json
import os
import re
from PIL import Image, ImageChops

def trim_white_border(im):
    bg = Image.new(im.mode, im.size, im.getpixel((0,0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)
    return im

def main():
    new_dir = r"c:\Movies\quotation-ai\quotation-ai\backend\static\images\Kohler\new"
    base_dir = r"c:\Movies\quotation-ai\quotation-ai\backend"
    os.makedirs(new_dir, exist_ok=True)
    
    # 1. Load needed variants
    list_path = r"C:\Users\DELL\.gemini\antigravity\brain\b7f2ef89-1581-40f1-a7cd-48870bb9dcdc\final_extraction_list.md"
    needed_variants = set()
    with open(list_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('- '):
                code = line[2:].split('(')[0].strip().lower()
                if "variants" not in code and "missing" not in code and "updated" not in code:
                    needed_variants.add(code)
                    
    print(f"Loaded {len(needed_variants)} needed variants.")
    
    # 2. Map codes to raw jpg paths using search_index_v2.json
    index_path = r"c:\Movies\quotation-ai\quotation-ai\backend\search_index_v2.json"
    with open(index_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    code_to_jpg = {}
    for item in data.get('stored_items', []):
        if item.get('brand', '').lower() == 'kohler':
            s_code = str(item.get('search_code', '')).strip().lower()
            b_code = str(item.get('base_code', '')).strip().lower()
            imgs = item.get('images', [])
            
            # Use original PDF jpg path if available.
            # If the json has '/static/images/Kohler/K-123.png?v=...', we need to fallback
            # But wait! search_index_v2.json has ALREADY replaced 'images' with the Kohler/ PNG paths in the previous steps!
            # Let's check if it still has the raw jpg paths.
            # If it has Kohler/ paths, we MUST use 1473_items_dump.json!
            pass

    # 3. Map codes to raw jpg paths using 1473_items_dump.json
    dump_path = r"c:\Movies\quotation-ai\quotation-ai\backend\1473_items_dump.json"
    with open(dump_path, 'r', encoding='utf-8') as f:
        raw_items = json.load(f)
        
    for item in raw_items:
        name = str(item.get('name', ''))
        imgs = item.get('images', [])
        if not imgs:
            continue
            
        raw_jpg = imgs[0]
        if raw_jpg.startswith('/'):
            raw_jpg = raw_jpg[1:]
        raw_jpg = os.path.join(base_dir, raw_jpg.replace('/', os.sep))
        
        # Exact code extraction from name
        codes = re.findall(r'\b(?:K-|EX)[A-Z0-9-]+\b', name)
        if not codes:
            m = re.search(r'\((.*?)\)$', name)
            code = m.group(1).strip().lower() if m else name.strip().lower()
        else:
            code = codes[-1].lower()
            
        code = code.replace('/', '-')
        
        # Map this specific code to the JPG
        code_to_jpg[code] = raw_jpg
        
        # Fallback: if name looks like "Desc (K-12345-CP)", map K-12345-CP
        m = re.search(r'\((.*?)\)$', name)
        if m:
            code_in_paren = m.group(1).strip().lower().replace('/', '-')
            code_to_jpg[code_in_paren] = raw_jpg

    extracted_count = 0
    found_variants = set()
    
    for v in needed_variants:
        raw_jpg_path = code_to_jpg.get(v)
        
        # If no exact match, try stripping finishes until we match a base code
        if not raw_jpg_path and '-' in v:
            parts = v.split('-')
            # Try removing the last part
            base_try = "-".join(parts[:-1])
            raw_jpg_path = code_to_jpg.get(base_try)
            
        if raw_jpg_path and os.path.exists(raw_jpg_path):
            try:
                img = Image.open(raw_jpg_path).convert('RGB')
                img_trimmed = trim_white_border(img)
                
                save_path = os.path.join(new_dir, f"{v.upper()}.png")
                img_trimmed.save(save_path, "PNG")
                found_variants.add(v)
                extracted_count += 1
                # print(f"Extracted {v.upper()} from {os.path.basename(raw_jpg_path)}")
            except Exception as e:
                print(f"Error processing {v.upper()}: {e}")
                
    print(f"Successfully extracted {extracted_count} images out of {len(needed_variants)} needed.")
    missing = needed_variants - found_variants
    if missing:
        print(f"Failed to find mapping for {len(missing)} variants.")

if __name__ == '__main__':
    main()
