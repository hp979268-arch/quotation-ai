import fitz
import re
from PIL import Image
import io

MARCH_PDF = r"backend/uploads/Kohler_PriceBook (June'26).pdf"
doc = fitz.open(MARCH_PDF)

def extract_test_image(code, target_page_num=None):
    print(f"Testing {code}...")
    found_page = None
    code_bbox = None
    
    # Find page and code bbox
    pages_to_search = [target_page_num-1] if target_page_num else range(len(doc))
    
    for pn in pages_to_search:
        page = doc[pn]
        text_dict = page.get_text("dict")
        base_code = code.rsplit('-', 1)[0]
        
        for block in text_dict["blocks"]:
            if block.get('type') != 0: continue
            for line in block.get('lines', []):
                lt = ' '.join(s['text'] for s in line.get('spans', []))
                if code in lt or (len(base_code) > 8 and base_code in lt):
                    code_bbox = block['bbox']
                    found_page = page
                    break
            if code_bbox: break
        if code_bbox: break
        
    if not code_bbox:
        print("Code not found.")
        return
        
    print(f"Found on page {found_page.number + 1} at Y: {code_bbox[1]:.1f} - {code_bbox[3]:.1f}")
    
    # Get all images
    all_images = []
    for img_info in found_page.get_images(full=True):
        xref = img_info[0]
        for rect in found_page.get_image_rects(xref):
            all_images.append({'xref': xref, 'rect': rect})
            
    # Find image with overlapping Y coordinates
    code_cy = (code_bbox[1] + code_bbox[3]) / 2
    best_img = None
    best_dist = float('inf')
    
    for img in all_images:
        r = img['rect']
        img_cy = (r.y0 + r.y1) / 2
        # Vertical distance
        dist = abs(img_cy - code_cy)
        
        # If it's roughly on the same row (within 50 points)
        if dist < 50:
            if dist < best_dist:
                best_dist = dist
                best_img = img
                
    if not best_img:
        print("No matching image found on the same row.")
        return
        
    r = best_img['rect']
    print(f"Matched image at Y: {r.y0:.1f} - {r.y1:.1f} (dist: {best_dist:.1f})")
    
    # Extract the embedded image
    img_data = doc.extract_image(best_img['xref'])
    pil_img = Image.open(io.BytesIO(img_data['image']))
    if pil_img.mode == 'CMYK': pil_img = pil_img.convert('RGB')
    elif pil_img.mode == 'RGBA':
        bg = Image.new('RGB', pil_img.size, (255,255,255))
        bg.paste(pil_img, mask=pil_img.split()[3])
        pil_img = bg
    elif pil_img.mode != 'RGB': pil_img = pil_img.convert('RGB')
    
    print(f"Extracted size: {pil_img.size}")
    out_path = f"backend/test_{code}.png"
    pil_img.save(out_path)
    print(f"Saved to {out_path}\n")

extract_test_image('K-73159IN-7-CP')
extract_test_image('K-26347IN-9-AF')

doc.close()
