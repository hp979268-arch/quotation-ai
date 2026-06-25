import fitz
import os
import re

def re_extract_final_images(pdf_path):
    doc = fitz.open(pdf_path)
    output_dir = r"backend\static\images\Kohler"
    
    extracted = []
    
    for page_num, page in enumerate(doc):
        blocks = page.get_text('blocks')
        drawings = page.get_drawings()
        
        h_lines = []
        for d in drawings:
            for item in d["items"]:
                if item[0] == "l":
                    p1, p2 = item[1], item[2]
                    if abs(p1.y - p2.y) < 1:
                        h_lines.append(p1.y)
                        
        h_lines.sort()
        
        for b in blocks:
            text = b[4].lower()
            if "trim + valve" in text or "trim & valve" in text:
                # Find the code
                match = re.search(r'K-\d+[A-Z0-9-]*', b[4])
                if match:
                    code = match.group(0).strip()
                    
                    text_center_y = (b[1] + b[3]) / 2
                    
                    y_above = 0
                    y_below = page.rect.height
                    
                    for y in h_lines:
                        if y < text_center_y and y > y_above:
                            y_above = y
                        if y > text_center_y and y < y_below:
                            y_below = y
                            
                    if text_center_y - y_above > 100: y_above = text_center_y - 40
                    if y_below - text_center_y > 100: y_below = text_center_y + 40
                    
                    # Ensure minimum height
                    if y_below - y_above < 20:
                        y_above = text_center_y - 30
                        y_below = text_center_y + 30
                        
                    box_rect = fitz.Rect(40, y_above + 1, 130, y_below - 1)
                    pix = page.get_pixmap(clip=box_rect, dpi=300)
                    
                    filename = code + "_FINAL.png"
                    out_path = os.path.join(output_dir, filename)
                    pix.save(out_path)
                    extracted.append(code)
                    print(f"Re-extracted {code} to {filename}")
                    
    return extracted

if __name__ == "__main__":
    print("Re-extracting missing FINAL images...")
    
    pdfs = [
        r"backend/uploads/Kohler_PriceBook (June'26).pdf",
        r"backend/uploads/Kohler_PriceBook (June'26).pdf"
    ]
    
    total = 0
    for pdf in pdfs:
        print(f"Processing {pdf}...")
        try:
            extracted = re_extract_final_images(pdf)
            total += len(extracted)
        except Exception as e:
            print(f"Error on {pdf}: {e}")
            
    print(f"Extracted {total} _FINAL images total.")
