import fitz
import re

def find_trim_valve_products(pdf_path):
    doc = fitz.open(pdf_path)
    count = 0
    products = []
    for page in doc:
        blocks = page.get_text('blocks')
        for b in blocks:
            text = b[4].lower()
            if "trim + valve" in text or "trim & valve" in text:
                # Find the K- code
                match = re.search(r'K-\d+[A-Z0-9-]*', b[4])
                if match:
                    products.append(match.group(0))
                    count += 1
    return count, list(set(products))

march_c, march_p = find_trim_valve_products(r"uploads/Kohler_PriceBook (June'26).pdf")
june_c, june_p = find_trim_valve_products(r"uploads/Kohler_PriceBook (June'26).pdf")

print(f"March: {march_c} occurrences, {len(march_p)} unique products")
print(f"June: {june_c} occurrences, {len(june_p)} unique products")

print("\nJune products with trim + valve:")
for p in sorted(june_p):
    print(p)
