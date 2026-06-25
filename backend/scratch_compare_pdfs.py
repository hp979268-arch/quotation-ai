import fitz

def find_22786(pdf_path):
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        text = page.get_text()
        if "22786" in text:
            print(f"Found 22786 in {pdf_path} on page {i}")
            
find_22786(r"uploads/Kohler_PriceBook (June'26).pdf")
find_22786(r"uploads/Kohler_PriceBook (June'26).pdf")
