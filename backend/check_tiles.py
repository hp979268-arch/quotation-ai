import fitz

MARCH_PDF = r"backend/uploads/Kohler_PriceBook (June'26).pdf"
JUNE_PDF = r"backend/uploads/Kohler_PriceBook (June'26).pdf"

doc_march = fitz.open(MARCH_PDF)
doc_june = fitz.open(JUNE_PDF)

print(f"March page 46 images: {len(doc_march[45].get_images(full=True))}")
print(f"June page 46 images: {len(doc_june[45].get_images(full=True))}")

doc_march.close()
doc_june.close()
