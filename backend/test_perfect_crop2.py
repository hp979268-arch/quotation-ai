import os, fitz
from PIL import Image

sc = 'EX28093IN-8-AF'
JUNE_PDF = r"backend/uploads/Kohler_PriceBook (June'26).pdf"

doc = fitz.open(JUNE_PDF)
page = doc[96]

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

# Collect all image rects on the page (left side)
img_rects = []
for img_info in page.get_images(full=True):
    xref = img_info[0]
    for r in page.get_image_rects(xref):
        if r.x0 < 250:
            img_rects.append(r)

primary_rect = min(img_rects, key=lambda r: min(abs(r.y0 - found_y), abs(r.y1 - found_y)))

# Group ONLY touching rects (tolerance = 1.5 pixels)
cluster = [primary_rect]
added = True
while added:
    added = False
    for r in img_rects:
        if r in cluster: continue
        # Calculate distance
        for c in cluster:
            # Shortest distance between rects
            dx = max(0, max(r.x0 - c.x1, c.x0 - r.x1))
            dy = max(0, max(r.y0 - c.y1, c.y0 - r.y1))
            dist = (dx**2 + dy**2)**0.5
            if dist <= 1.5:
                cluster.append(r)
                added = True
                break

final_rect = fitz.Rect(cluster[0])
for r in cluster[1:]:
    final_rect.include_rect(r)

# Render with Zoom=3
zoom = 3
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat)
full_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

# Crop coordinates in pixels
crop_x0 = int(final_rect.x0 * zoom)
crop_y0 = int(final_rect.y0 * zoom)
crop_x1 = int(final_rect.x1 * zoom)
crop_y1 = int(final_rect.y1 * zoom)

cropped = full_img.crop((crop_x0, crop_y0, crop_x1, crop_y1))

# Paste on white canvas with margins (e.g. 20px padding)
canvas_w = cropped.width + int(30 * zoom)
canvas_h = cropped.height + int(20 * zoom)
canvas = Image.new('RGB', (canvas_w, canvas_h), (255, 255, 255))
canvas.paste(cropped, (int(15 * zoom), int(10 * zoom)))

canvas.save("backend/test_perfect_crop2.png")
print("Saved backend/test_perfect_crop2.png")
doc.close()
