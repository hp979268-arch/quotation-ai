import pdfplumber
import re
import json

def main():
    pdf_path = 'c:/Movies/quotation-ai/quotation-ai/backend/uploads/Kohler_PriceBook (June\'26).pdf'
    index_path = 'c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json'
    
    with open(index_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    json_codes = set()
    for item in data.get('stored_items', []):
        if item.get('brand', '').lower() == 'kohler':
            code = str(item.get('search_code', '')).strip().upper()
            if code:
                json_codes.add(code)
            bc = str(item.get('base_code', '')).strip().upper()
            if bc:
                json_codes.add(bc)
                
    pdf_codes = set()
    code_pattern = re.compile(r'\b(K-[0-9]{4,7}[A-Z0-9-]*|EX[0-9]{4,7}[A-Z0-9-]*)\b', re.IGNORECASE)
    
    print("Scanning PDF for all codes...")
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                codes = code_pattern.findall(text)
                for c in codes:
                    # Clean trailing hyphens or weird chars
                    c_clean = c.strip('-').upper()
                    pdf_codes.add(c_clean)
                    
    # Find codes in PDF that are NOT in JSON
    missing_from_json = pdf_codes - json_codes
    
    # Filter out obvious non-products or short references if needed, but let's see the raw count
    missing_list = sorted(list(missing_from_json))
    
    print(f"Total codes in JSON: {len(json_codes)}")
    print(f"Total unique codes in PDF: {len(pdf_codes)}")
    print(f"Codes in PDF but MISSING in JSON: {len(missing_list)}")
    
    with open('c:/Movies/quotation-ai/quotation-ai/backend/pdf_missing_analysis.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(missing_list))

if __name__ == '__main__':
    main()
