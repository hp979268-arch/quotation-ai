import fitz
import os

pdf_path = "uploads/Kohler_PriceBook (June'26).pdf"
output_dir = "tmp_page_164"
os.makedirs(output_dir, exist_ok=True)

doc = fitz.open(pdf_path)
page_num = 164
page = doc[page_num]

print(f"Page {page_num} size: {page.rect}")

# Search for the code to get its position
keywords = ["26475", "Span", "Urinal"]
for kw in keywords:
    text_instances = page.search_for(kw)
    for i, inst in enumerate(text_instances):
        print(f"Keyword '{kw}' instance {i} at {inst}")

images = page.get_images(full=True)
print(f"Found {len(images)} images on page {page_num}")

for i, img in enumerate(images):
    xref = img[0]
    base_image = doc.extract_image(xref)
    image_bytes = base_image["image"]
    ext = base_image["ext"]
    
    # Get rects
    rects = page.get_image_rects(xref)
    rect = rects[0] if rects else None
    
    filename = f"img_{i}_{xref}.{ext}"
    with open(os.path.join(output_dir, filename), "wb") as f:
        f.write(image_bytes)
    
    print(f"Extracted {filename} at rect {rect}")
