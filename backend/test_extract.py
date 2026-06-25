import fitz, io, os
from PIL import Image

pdf_path = r"c:\Movies\quotation-ai\quotation-ai\backend\uploads\Kohler_PriceBook (June'26).pdf"
doc = fitz.open(pdf_path)
page = doc[110]
print(f"Images on page 111: {len(page.get_images(full=True))}")

images = page.get_images(full=True)
for img_info in images:
    xref = img_info[0]
    base_image = doc.extract_image(xref)
    image_bytes = base_image["image"]
    image_ext = base_image["ext"]
    image = Image.open(io.BytesIO(image_bytes))
    print(f"Extracted image {xref} {image.size}")
doc.close()
