import fitz  # PyMuPDF
import os

# PDF aur output folder ka path
doc_path = r"backend/uploads/Kohler_PriceBook (June'26).pdf"
output_dir = r"backend/static/images/Kohler"

# Output folder bana lo agar nahi hai
os.makedirs(output_dir, exist_ok=True)

def extract_images_from_pdf(pdf_path, output_folder):
    doc = fitz.open(pdf_path)
    img_count = 0
    for page_num in range(len(doc)):
        page = doc[page_num]
        images = page.get_images(full=True)
        for img_index, img in enumerate(images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            img_filename = f"Kohler_p{page_num+1}_i{img_index+1}.{image_ext}"
            img_path = os.path.join(output_folder, img_filename)
            with open(img_path, "wb") as img_file:
                img_file.write(image_bytes)
            img_count += 1
    print(f"Total images extracted: {img_count}")

if __name__ == "__main__":
    extract_images_from_pdf(doc_path, output_dir)
    print("Extraction complete. Check the Kohler folder.")
