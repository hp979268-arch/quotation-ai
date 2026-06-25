import os
import re
from pdf_reader import extract_content

def main():
    pdf_path = r"c:\Movies\quotation-ai\quotation-ai\backend\uploads\Kohler_PriceBook (June'26).pdf"
    image_dir = r"c:\Movies\quotation-ai\quotation-ai\backend\static\images\Kohler"
    
    items = extract_content(pdf_path)
    exist = {f.lower() for f in os.listdir(image_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))}
    
    missing_codes = []
    
    for i in items:
        name = str(i.get('name', ''))
        code = ''
        
        # Try to extract the code from parentheses e.g. "Product Name (K-12345)"
        m = re.search(r'\((.*?)\)$', name)
        if m:
            code = m.group(1).strip()
        else:
            # Maybe the whole name is the code? Or no code exists.
            code = name.strip()
            
        if not code:
            continue
            
        # Check if {code}.png exists
        if f"{code.lower()}.png" not in exist and f"{code.lower()}.jpg" not in exist:
            missing_codes.append(code)
            
    print(f"Total extracted from PDF: {len(items)}")
    print(f"Total Missing Images: {len(missing_codes)}")
    
    with open('c:/Movies/quotation-ai/quotation-ai/backend/exact_missing_1473.txt', 'w', encoding='utf-8') as f:
        for c in sorted(missing_codes):
            f.write(c + "\n")

if __name__ == '__main__':
    main()
