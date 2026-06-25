import fitz
from PIL import Image

doc = fitz.open(r"backend/uploads/Kohler_PriceBook (June'26).pdf")
page = doc[45]  # Page 46

# Render at 4x zoom for high quality
zoom = 4
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat)
full_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

print(f"Full image size: {full_img.width}x{full_img.height}")

# We know from earlier debug that images are at X=47 to X=111
# Let's crop X=40 to X=120
crop_x0 = int(40 * zoom)
crop_x1 = int(120 * zoom)

# And Y corresponds to the product.
# K-73159IN-7-CP is at Y ~ 290 to 350
crop_y0 = int(280 * zoom)
crop_y1 = int(360 * zoom)

cropped = full_img.crop((crop_x0, crop_y0, crop_x1, crop_y1))
cropped.save("backend/test_crop_clean.png")
print("Saved clean crop to backend/test_crop_clean.png")

# Now let's see what a "dual image" looks like.
# Let's find "Trim" and "Valve" text on page 114 (where K-23486IN-4ND-BV is)
p114 = doc[113]
text_dict = p114.get_text("dict")
for block in text_dict["blocks"]:
    if block.get('type') != 0: continue
    for line in block.get('lines', []):
        bt = ' '.join(s['text'] for s in line.get('spans',[]))
        if 'Trim' in bt or 'Valve' in bt:
            print(f"Header: {bt} at Y={block['bbox'][1]}")

doc.close()
