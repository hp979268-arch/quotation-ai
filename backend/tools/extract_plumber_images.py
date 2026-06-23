import os
import json
import fitz  # PyMuPDF
import re

INDEX_PATH = "search_index_v2.json"
IMG_ROOT = os.path.join("static", "images", "plumber")
PDF_PATH = os.path.join("uploads", "Plumber Bathware.pdf")

def compact_safe(s):
    return re.sub(r"[^A-Za-z0-9_-]", "", str(s).replace(" ", "_")).strip("_")

def main():
    if not os.path.exists(PDF_PATH):
        print(f"PDF not found at {PDF_PATH}")
        return

    data = json.load(open(INDEX_PATH, "r", encoding="utf-8-sig"))
    items = data.get("stored_items", [])
    
    # Identify items for Plumber
    plumber_items = []
    for item in items:
        brand = str(item.get("brand", "")).lower()
        if "plumber" in brand:
            plumber_items.append(item)

    print(f"Found {len(plumber_items)} Plumber items.")
    if not plumber_items:
        return

    # Group by page
    from collections import defaultdict
    by_page = defaultdict(list)
    for item in plumber_items:
        by_page[item.get("page", 0)].append(item)

    doc = fitz.open(PDF_PATH)
    os.makedirs(IMG_ROOT, exist_ok=True)
    
    fixed = 0
    
    for page_num, p_items in by_page.items():
        if page_num < 0 or page_num >= len(doc):
            continue
            
        page = doc[page_num]
        images = page.get_images(full=True)
        if not images:
            continue
            
        # Extract images and get their rects
        extracted_images = []
        for img_idx, img in enumerate(images):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                ext = base_image["ext"]
                rects = page.get_image_rects(xref)
                rect = rects[0] if rects else fitz.Rect()
                extracted_images.append({
                    "bytes": image_bytes,
                    "ext": ext,
                    "rect": rect,
                    "area": rect.get_area()
                })
            except Exception:
                continue
                
        if not extracted_images:
            continue

        for item in p_items:
            code = str(item.get("search_code", ""))
            safe_code = compact_safe(code)
            
            # Find the text rect
            text_rects = page.search_for(code)
            if not text_rects:
                # Try parts
                base = code.split("-")[0] if "-" in code else code
                text_rects = page.search_for(base)
                
            best_img = None
            if text_rects:
                t_rect = text_rects[0]
                min_dist = float('inf')
                for img_info in extracted_images:
                    ir = img_info["rect"]
                    # Center distance
                    dx = ir.x0 + ir.width/2 - (t_rect.x0 + t_rect.width/2)
                    dy = ir.y0 + ir.height/2 - (t_rect.y0 + t_rect.height/2)
                    dist = (dx**2 + dy**2) ** 0.5
                    
                    if dist < min_dist and img_info["area"] > 500:
                        min_dist = dist
                        best_img = img_info
            
            if not best_img:
                extracted_images.sort(key=lambda x: x["area"], reverse=True)
                for img_info in extracted_images:
                    if img_info["area"] > 500:
                        best_img = img_info
                        break
                        
            if best_img:
                filename = f"PB_{safe_code}.{best_img['ext']}"
                local_path = os.path.join(IMG_ROOT, filename)
                with open(local_path, "wb") as f:
                    f.write(best_img["bytes"])
                    
                public_path = f"/static/images/plumber/{filename}"
                item["images"] = [public_path]
                fixed += 1
                # print(f"Extracted: {code} -> {filename}")

    # Save index
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        
    print(f"\nSuccessfully extracted and assigned {fixed} images from Plumber PDF.")

if __name__ == "__main__":
    main()
