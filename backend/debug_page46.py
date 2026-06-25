"""
Debug: Check page 46 layout - where are images relative to text?
"""
import fitz
from PIL import Image

doc = fitz.open(r"backend/uploads/Kohler_PriceBook (June'26).pdf")
page = doc[45]  # Page 46

# Get all images with positions
print("=== IMAGES ON PAGE 46 ===")
all_images = []
for img_info in page.get_images(full=True):
    xref = img_info[0]
    rects = page.get_image_rects(xref)
    for rect in rects:
        w = rect.x1 - rect.x0
        h = rect.y1 - rect.y0
        print(f"  Image xref={xref}: rect=({rect.x0:.0f},{rect.y0:.0f},{rect.x1:.0f},{rect.y1:.0f}) size={w:.0f}x{h:.0f}")
        all_images.append({'xref': xref, 'rect': rect, 'w': w, 'h': h})

print(f"\nTotal images: {len(all_images)}")

# Get text blocks with product codes
print("\n=== TEXT WITH PRODUCT CODES ON PAGE 46 ===")
text_dict = page.get_text("dict")
for block in text_dict["blocks"]:
    if block.get('type') != 0:
        continue
    bt = ' '.join(s['text'] for l in block.get('lines',[]) for s in l.get('spans',[]))
    if 'K-' in bt and ('25757' in bt or '25759' in bt or '25758' in bt or '73050' in bt or '73159' in bt):
        print(f"  Code block: '{bt[:100]}' at bbox={[round(x,0) for x in block['bbox']]}")

# Save rendered page for visual inspection  
mat = fitz.Matrix(2, 2)
pix = page.get_pixmap(matrix=mat)
img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
img.save("backend/page46_debug.png")
print("\nSaved: backend/page46_debug.png")

doc.close()
