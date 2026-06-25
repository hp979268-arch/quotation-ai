import os
import re
import math
from PIL import Image
from pdf_reader import extract_content

def ahash(img):
    img = img.resize((8, 8), Image.Resampling.LANCZOS).convert("L")
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join(['1' if p > avg else '0' for p in pixels])
    return int(bits, 2)

def hamming_distance(h1, h2):
    return bin(h1 ^ h2).count('1')

def make_white_bg(img):
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        bg.paste(img, mask=img.split()[3])
        return bg
    return img.convert('RGB')

def main():
    pdf_path = r"c:\Movies\quotation-ai\quotation-ai\backend\uploads\Kohler_PriceBook (June'26).pdf"
    
    print("Extracting fresh images from PDF...")
    items = extract_content(pdf_path)
    
    png_dir = r"c:\Movies\quotation-ai\quotation-ai\backend\static\images\Kohler"
    base_dir = r"c:\Movies\quotation-ai\quotation-ai\backend"
    
    updated_count = 0
    updated_codes = []
    
    for i in items:
        name = str(i.get('name', ''))
        m = re.search(r'\((.*?)\)$', name)
        code = m.group(1).strip() if m else name.strip()
        code = code.lower().replace('/', '-')
        
        png_path = os.path.join(png_dir, f"{code}.png")
        if not os.path.exists(png_path):
            png_path = os.path.join(png_dir, f"{code}.jpg")
            
        if os.path.exists(png_path) and i.get('images'):
            raw_jpg_rel = i.get('images')[0]
            if raw_jpg_rel.startswith('/'):
                raw_jpg_rel = raw_jpg_rel[1:]
            raw_jpg_path = os.path.join(base_dir, raw_jpg_rel.replace('/', os.sep))
            
            if os.path.exists(raw_jpg_path):
                try:
                    img_png = Image.open(png_path)
                    img_png = make_white_bg(img_png)
                    img_jpg = Image.open(raw_jpg_path).convert('RGB')
                    
                    h1 = ahash(img_png)
                    h2 = ahash(img_jpg)
                    
                    dist = hamming_distance(h1, h2)
                    
                    # If distance is > 15 out of 64, it's likely a structurally different image
                    if dist > 15:
                        updated_count += 1
                        updated_codes.append(code)
                except Exception as e:
                    pass
                    
    print(f"\nTotal images found in both places: {len(items)}")
    print(f"Total UPDATED images: {updated_count}")
    
    with open('c:/Movies/quotation-ai/quotation-ai/backend/updated_images.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(updated_codes))

if __name__ == '__main__':
    main()
