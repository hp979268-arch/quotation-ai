import fitz

pdf_path = "uploads/Kohler_PriceBook (June'26).pdf"
doc = fitz.open(pdf_path)

found = False
for i, page in enumerate(doc):
    text = page.get_text()
    if "26475" in text:
        print(f"MATCH on Page {i}")
        print(page.search_for("26475"))
        found = True

if not found:
    print("No match found for 26475")
