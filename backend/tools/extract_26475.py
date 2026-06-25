import fitz
import os

PDF_PATH = os.path.join("uploads", "Kohler_PriceBook (June'26).pdf")
IMG_ROOT = os.path.join("static", "images", "kohler")
CODE = "K-26475IN-ER 0"

# Based on old name, it's on page 163 (0-indexed or 1-indexed? Usually 1-indexed in old names, so 162 in fitz)
doc = fitz.open(PDF_PATH)
for page_num in range(160, 165):
    page = doc[page_num]
    text = page.get_text()
    if "26475" in text:
        print(f"Found on page {page_num}")
        images = page.get_images(full=True)
        if images:
            for i, img in enumerate(images):
                try:
                    base_image = doc.extract_image(img[0])
                    image_bytes = base_image["image"]
                    ext = base_image["ext"]
                    filename = f"K-26475IN-ER-0_{i}.{ext}"
                    with open(os.path.join(IMG_ROOT, filename), "wb") as f:
                        f.write(image_bytes)
                    print(f"Saved {filename} ({len(image_bytes)} bytes)")
                except Exception as e:
                    print("Error extracting:", e)
