import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import os
import re

# Set Tesseract executable path (Updated ✅)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# PDF aur output folder ka path
doc_path = r"backend/uploads/Kohler_Pricebook (March'26).pdf"
output_dir = r"backend/static/images/Kohler"

# Output folder bana lo agar nahi hai
os.makedirs(output_dir, exist_ok=True)

# Product code pattern (K-XXXXXIN-XX-X)
code_pattern = re.compile(r"K-\d{5,6}IN-[A-Z0-9-]+")

def extract_images_with_code(pdf_path, output_folder):
    doc = fitz.open(pdf_path)
    img_count = 0
    for page_num in range(len(doc)):
        page = doc[page_num]
        images = page.get_images(full=True)
        # Page image for OCR
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes()
        pil_img = Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(pil_img)
        codes = code_pattern.findall(text)
        code = codes[0] if codes else f"page{page_num+1}"
        for img_index, img in enumerate(images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            img_filename = f"{code}.{image_ext}"
            img_path = os.path.join(output_folder, img_filename)
            with open(img_path, "wb") as img_file:
                img_file.write(image_bytes)
            img_count += 1
    print(f"Total images extracted: {img_count}")

if __name__ == "__main__":
    extract_images_with_code(doc_path, output_dir)
    print("Extraction complete. Check the Kohler folder.")
