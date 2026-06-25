import os, fitz
from PIL import Image

sc = 'EX28093IN-8-AF'
JUNE_PDF = r"backend/uploads/Kohler_PriceBook (June'26).pdf"

doc = fitz.open(JUNE_PDF)

# We know it's on page 97
page = doc[96]

def rect_distance(r1, r2):
    dx = max(0, max(r1.x0 - r2.x1, r2.x0 - r1.x1))
    dy = max(0, max(r1.y0 - r2.y1, r2.y0 - r1.y1))
    return (dx**2 + dy**2)**0.5

# Find y of the text
blocks = page.get_text("dict")["blocks"]
base = "EX28093IN-8"
found_y = None

for b in blocks:
    if "lines" not in b: continue
    for l in b["lines"]:
        for s in l["spans"]:
            text = s["text"].strip()
            if text == base or text == sc:
                found_y = s["bbox"][1]
                break
        if found_y: break
    if found_y: break
    
# Collect all image rects on the page
img_rects = []
for img_info in page.get_images(full=True):
    xref = img_info[0]
    for r in page.get_image_rects(xref):
        if r.x0 < 250:
            img_rects.append(r)

primary_rect = min(img_rects, key=lambda r: min(abs(r.y0 - found_y), abs(r.y1 - found_y)))

cluster = [primary_rect]
added = True
while added:
    added = False
    for r in img_rects:
        if r in cluster: continue
        # Tolerance increased to 40 pixels to catch separated handles/spouts
        for c in cluster:
            if rect_distance(r, c) < 40:
                cluster.append(r)
                added = True
                break

final_rect = fitz.Rect(cluster[0])
for r in cluster[1:]:
    final_rect.include_rect(r)

final_rect = final_rect + (-2, -2, 2, 2)

pix = page.get_pixmap(clip=final_rect, matrix=fitz.Matrix(3, 3))
img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

# Now instead of saving this weirdly sized crop directly, 
# we paste it onto a nice white canvas with standard margins
# Standard width for previous images was roughly 90*3 = 270px width (from 35 to 125 zoom 3)
canvas_w = max(270, img.width + 40)
canvas_h = max(270, img.height + 40)

canvas = Image.new('RGB', (canvas_w, canvas_h), (255, 255, 255))
# Center it
offset_x = (canvas_w - img.width) // 2
offset_y = (canvas_h - img.height) // 2
canvas.paste(img, (offset_x, offset_y))

canvas.save("backend/test_perfect_crop.png")
print("Saved backend/test_perfect_crop.png")
