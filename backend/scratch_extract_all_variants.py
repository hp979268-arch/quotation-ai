import fitz
import os
import re
import json
from dotenv import load_dotenv
load_dotenv()
import mongodb

def extract_all_variants(pdf_path, index_file):
    with open(index_file, "r", encoding="utf-8") as f:
        db = json.load(f)
        
    codes = [i['search_code'] for i in db['stored_items'] if 'trim + valve' in i.get('text', '').lower() or 'trim + valve' in i.get('name', '').lower()]
    codes = list(set(codes))
    print(f"Found {len(codes)} variants to process.")
    
    doc = fitz.open(pdf_path)
    output_dir = r"static\images\Kohler"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
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
            for code in codes:
                if code in b[4]:
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
                    if y_below - y_above < 30:
                        y_above -= 10
                        y_below += 10
                    
                    # Box rect: from X=30 to the start of the text block X0 - 5
                    box_rect = fitz.Rect(30, y_above + 1, b[0] - 5, y_below - 1)
                    
                    # Only extract if valid
                    if box_rect.width > 20 and box_rect.height > 20:
                        pix = page.get_pixmap(clip=box_rect, dpi=300)
                        
                        filename = code + "_FINAL.png"
                        out_path = os.path.join(output_dir, filename)
                        pix.save(out_path)
                        extracted.append((code, filename))
                        print(f"Extracted {code} to {filename}")
                    
    # Deduplicate extracted list
    unique_extracted = {code: filename for code, filename in extracted}
    
    for code, filename in unique_extracted.items():
        for item in db["stored_items"]:
            if code == item.get("search_code", ""):
                item["images"] = ["/static/images/Kohler/" + filename]
                
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(db, f)

    print("Updated search_index_v2.json!")

    try:
        mongodb.save_search_index(db)
        print("Updated MongoDB search index!")
    except Exception as e:
        print("Failed to update MongoDB:", e)

if __name__ == "__main__":
    extract_all_variants(r"uploads/Kohler_PriceBook (June'26).pdf", "search_index_v2.json")
