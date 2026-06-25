import fitz
import sys

def search_text(pdf_path, page_num):
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    blocks = page.get_text('blocks')
    for b in blocks:
        if "22786" in b[4]:
            print("Found block:", b)

print("March:")
search_text(r"uploads/Kohler_PriceBook (June'26).pdf", 112)
print("June:")
search_text(r"uploads/Kohler_PriceBook (June'26).pdf", 114)
