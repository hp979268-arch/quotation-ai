import json
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
    os.makedirs(new_dir, exist_ok=True)
    
    # Load the list of 266 variants
    list_path = r"C:\Users\DELL\.gemini\antigravity\brain\b7f2ef89-1581-40f1-a7cd-48870bb9dcdc\final_extraction_list.md"
    needed_variants = set()
    with open(list_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('- '):
                # e.g. "- K-1234-CP" or "- K-1234-CP (something)"
                code = line[2:].split('(')[0].strip().lower()
                # don't add "Missing Images: 146 variants" lines
                if "variants" not in code and "missing" not in code and "updated" not in code:
                    needed_variants.add(code)
                    
    print(f"Loaded {len(needed_variants)} needed variants.")
    
    print("Extracting items from PDF (this may take a minute if cache is missing)...")
    items = extract_content(pdf_path)
    
    extracted_count = 0
    base_dir = r"c:\Movies\quotation-ai\quotation-ai\backend"
    
    # Track which ones we found
    found_variants = set()
    
    for i in items:
        name = str(i.get('name', ''))
        # Try to find the base code
        codes = re.findall(r'\b(?:K-|EX)[A-Z0-9-]+\b', name)
        
        if not codes:
            m = re.search(r'\((.*?)\)$', name)
            if m:
                code = m.group(1).strip()
            else:
                code = name.strip()
        else:
            code = codes[-1]
            
        base_code = code.lower().replace('/', '-')
        
        # Check if this item matches ANY needed variant
        # E.g. base_code is "k-1234" and needed variant is "k-1234-cp"
        # Since pdf_reader's items usually just have the base code (or the first variant code),
        # we need to see if the base_code matches, OR if any needed variant starts with this base_code.
        
        matched_variants = []
        for v in needed_variants:
            # exact match
            if base_code == v:
                matched_variants.append(v)
            # or it's a finish variant of the base code (e.g. k-1234-cp starts with k-1234)
            elif v.startswith(base_code + "-"):
                matched_variants.append(v)
            # handle cases where the pdf item has a finish but needed is a different finish?
            # actually if the pdf item is "k-1234-cp", then base_code="k-1234-cp". 
            # If needed is "k-1234-af", we should still map it if it's the same base product!
            # Let's strip the last finish to check.
            elif "-" in base_code and v.startswith(base_code.rsplit("-", 1)[0] + "-"):
                matched_variants.append(v)
                
        # Also check exact name match for those weird ones like "FAUCET CLEANER"
        for v in needed_variants:
            if v == name.lower().strip():
                if v not in matched_variants:
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
                
                # Save it for ALL matched variants!
                for v in matched_variants:
                    if v not in found_variants:
                        save_path = os.path.join(new_dir, f"{v.upper()}.png")
                        img_trimmed.save(save_path, "PNG")
                        found_variants.add(v)
                        extracted_count += 1
                        print(f"Extracted image for {v.upper()}")
            except Exception as e:
                print(f"Error processing {raw_jpg_path}: {e}")
                
    print(f"Successfully extracted {extracted_count} images out of {len(needed_variants)} needed.")
    missing_after = needed_variants - found_variants
    if missing_after:
        print(f"Still missing {len(missing_after)} variants: {missing_after}")

if __name__ == '__main__':
    main()
