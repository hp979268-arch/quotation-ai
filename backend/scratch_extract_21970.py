import fitz
import os
import json
from dotenv import load_dotenv
load_dotenv()
import mongodb

def extract_21970(pdf_path, index_file):
    with open(index_file, "r", encoding="utf-8") as f:
        db = json.load(f)
        
    code = "K-21970IN-4ND-RGD"
    
    doc = fitz.open(pdf_path)
    output_dir = r"static\images\Kohler"
    
    extracted = []
    
    # We found it on page 122 (index 122 in my script? fitz is 0-indexed)
    # The output from script was 122, so page index is 122.
    page = doc[122]
    
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
            
            if y_below - y_above < 30:
                y_above -= 10
                y_below += 10
            
            # The right edge of the image is just before the text
            box_rect = fitz.Rect(30, y_above + 1, b[0] - 5, y_below - 1)
            
            if box_rect.width > 20 and box_rect.height > 20:
                pix = page.get_pixmap(clip=box_rect, dpi=300)
                
                filename = code + "_FINAL.png"
                out_path = os.path.join(output_dir, filename)
                pix.save(out_path)
                extracted.append((code, filename))
                print(f"Extracted {code} to {filename}")

    if extracted:
        for code, filename in extracted:
            for item in db["stored_items"]:
                if code == item.get("search_code", ""):
                    item["images"] = ["/static/images/Kohler/" + filename]
                    print("Updated JSON for", code)
                    
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(db, f)

        try:
            mongodb.save_search_index(db)
            print("Updated MongoDB search index!")
        except Exception as e:
            print("Failed to update MongoDB:", e)
    else:
        print("Failed to extract image!")

if __name__ == "__main__":
    extract_21970(r"uploads/Kohler_PriceBook (June'26).pdf", "search_index_v2.json")
