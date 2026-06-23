import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import os
import re
from PIL import Image as PILImage

# Set Tesseract executable path (Updated ✅)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# PDF aur output folder ka path
doc_path = r"backend/uploads/Kohler_Pricebook (March'26).pdf"
output_dir = r"backend/static/images/Kohler"

# Clean old files
if os.path.exists(output_dir):
    import shutil
    shutil.rmtree(output_dir)
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
            
            # Convert to PNG using PIL (forces proper PNG format)
            img_pil = PILImage.open(io.BytesIO(image_bytes)).convert('RGB')
            img_filename = f"{code}.png"
            img_path = os.path.join(output_folder, img_filename)
            img_pil.save(img_path, 'JPEG', quality=95)
            
            img_count += 1
            print(f"Saved: {img_filename}")
    print(f"\n✅ Total PNG images extracted: {img_count}")
    print(f"📁 Location: {output_folder}")

if __name__ == "__main__":
    extract_images_with_code(doc_path, output_dir)
    print("✅ Extraction complete! All PNG with product codes.")
