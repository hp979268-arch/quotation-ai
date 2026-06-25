import fitz
import os

pdf_path = "uploads/Kohler_PriceBook (June'26).pdf"
doc = fitz.open(pdf_path)
page = doc[163]
target_rect = fitz.Rect(419.93, 165.11, 442.42, 174.61)

print(f"Target text at {target_rect}")

images = page.get_images(full=True)
os.makedirs("urinal_fix", exist_ok=True)

best_img = None
min_dist = float('inf')

for i, img in enumerate(images):
    xref = img[0]
    rects = page.get_image_rects(xref)
    if not rects: continue
    
    ir = rects[0]
    # Center distance
    dx = (ir.x0 + ir.x1)/2 - (target_rect.x0 + target_rect.x1)/2
    dy = (ir.y0 + ir.y1)/2 - (target_rect.y0 + target_rect.y1)/2
    dist = (dx**2 + dy**2)**0.5
    
    print(f"Image {i} (xref {xref}) at {ir}, dist: {dist}")
    
    if dist < min_dist:
        min_dist = dist
        best_img = (xref, ir)

if best_img:
    xref, ir = best_img
    pix = doc.extract_image(xref)
    filename = f"K-26475IN-ER-0_FIX.{pix['ext']}"
    with open(os.path.join("static", "images", "Kohler", filename), "wb") as f:
        f.write(pix['image'])
    print(f"\nSAVED NEW IMAGE: {filename}")
else:
    print("No image found near target.")
