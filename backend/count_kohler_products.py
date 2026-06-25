import pdfplumber
import re

def main():
    pdf_path = 'c:/Movies/quotation-ai/quotation-ai/backend/uploads/Kohler_PriceBook (June\'26).pdf'
    
    mrp_pattern = re.compile(r'mrp[\s\`\']*[0-9,]+\.[0-9]{2}', re.IGNORECASE)
    code_pattern = re.compile(r'\b(K-[0-9]{4,7}[A-Z0-9-]*|EX[0-9]{4,7}[A-Z0-9-]*)\b', re.IGNORECASE)
    
    total_mrps = 0
    unique_codes = set()
    all_codes = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            
            mrps = mrp_pattern.findall(text)
            total_mrps += len(mrps)
            
            codes = code_pattern.findall(text)
            for c in codes:
                unique_codes.add(c.upper())
                all_codes.append(c.upper())
                
    print(f"Total MRP entries found: {total_mrps}")
    print(f"Total Unique K-/EX- Codes found: {len(unique_codes)}")
    print(f"Total K-/EX- Codes occurrences: {len(all_codes)}")

if __name__ == '__main__':
    main()
