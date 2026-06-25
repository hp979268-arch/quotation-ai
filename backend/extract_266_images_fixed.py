import os
import re
from PIL import Image, ImageChops

from pdf_reader import extract_content

def trim_white_border(im):
    bg = Image.new(im.mode, im.size, im.getpixel((0,0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)
    return im

def main():
    pdf_path = r"c:\Movies\quotation-ai\quotation-ai\backend\uploads\Kohler_PriceBook (June'26).pdf"
    new_dir = r"c:\Movies\quotation-ai\quotation-ai\backend\static\images\Kohler\new"
    
    # Load the list of 266 variants
    list_path = r"C:\Users\DELL\.gemini\antigravity\brain\b7f2ef89-1581-40f1-a7cd-48870bb9dcdc\final_extraction_list.md"
    needed_variants = set()
    with open(list_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('- '):
                code = line[2:].split('(')[0].strip().lower()
                if "variants" not in code and "missing" not in code and "updated" not in code:
                    needed_variants.add(code)
                    
    print(f"Loaded {len(needed_variants)} needed variants.")
    
    items = extract_content(pdf_path)
    base_dir = r"c:\Movies\quotation-ai\quotation-ai\backend"
    
    found_variants = set()
    extracted_count = 0
    
    for i in items:
        name = str(i.get('name', ''))
        codes = re.findall(r'\b(?:K-|EX)[A-Z0-9-]+\b', name)
        
        if not codes:
            m = re.search(r'\((.*?)\)$', name)
            code = m.group(1).strip() if m else name.strip()
        else:
            code = codes[-1]
            
        base_code = code.lower().replace('/', '-')
        
        matched_variants = []
        for v in needed_variants:
            if base_code == v:
                matched_variants.append(v)
            elif v.startswith(base_code + "-"):
                matched_variants.append(v)
            # Safe cross-variant matching (e.g. base=K-1234-AF, v=K-1234-CP)
            elif "-" in base_code:
                parts = base_code.split("-")
                # Ensure the base prefix contains digits (e.g. k-1234)
                if len(parts) >= 2 and any(char.isdigit() for char in parts[1]):
                    prefix = "-".join(parts[:-1]) # e.g. k-1234
                    if v.startswith(prefix + "-"):
                        matched_variants.append(v)
                        
        # Exact match for non-code items
        for v in needed_variants:
            if v == name.lower().strip() and v not in matched_variants:
                matched_variants.append(v)
                
        if not matched_variants:
            continue
            
        images = i.get('images', [])
        if not images:
            continue
            
        raw_jpg_rel = images[0]
        if raw_jpg_rel.startswith('/'):
            raw_jpg_rel = raw_jpg_rel[1:]
        raw_jpg_path = os.path.join(base_dir, raw_jpg_rel.replace('/', os.sep))
        
        if os.path.exists(raw_jpg_path):
            try:
                img = Image.open(raw_jpg_path).convert('RGB')
                img_trimmed = trim_white_border(img)
                
                for v in matched_variants:
                    if v not in found_variants:
                        save_path = os.path.join(new_dir, f"{v.upper()}.png")
                        img_trimmed.save(save_path, "PNG")
                        found_variants.add(v)
                        extracted_count += 1
                        print(f"Extracted image for {v.upper()} from {raw_jpg_path}")
            except Exception as e:
                print(f"Error processing {raw_jpg_path}: {e}")
                
    print(f"Successfully extracted {extracted_count} images out of {len(needed_variants)} needed.")

if __name__ == '__main__':
    main()
