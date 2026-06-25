import os
import re
import pdfplumber

def main():
    pdf_path = 'c:/Movies/quotation-ai/quotation-ai/backend/uploads/Kohler_PriceBook (June\'26).pdf'
    orphan_report = 'c:/Movies/quotation-ai/quotation-ai/backend/orphan_images_report.md'
    
    with open(orphan_report, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    orphans = []
    for line in lines:
        if line.startswith('- `'):
            fname = line.replace('- `', '').replace('`', '').strip()
            orphans.append(fname)
            
    print(f"Loaded {len(orphans)} orphans to check against PDF.")
    
    # Extract base codes to search
    search_queries = {}
    for o in orphans:
        # K-702239IN-LH0-AF.png -> 702239
        match = re.search(r'([0-9]{4,7})', o)
        if match:
            search_queries[o] = match.group(1)
        else:
            base = re.sub(r'\.(png|jpg|jpeg)$', '', o, flags=re.I)
            search_queries[o] = base.lower()
            
    found_in_pdf = {o: False for o in orphans}
    
    print("Scanning PDF text...")
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text: continue
            text_lower = text.lower()
            
            for o, q in search_queries.items():
                if not found_in_pdf[o]:
                    if q in text_lower:
                        found_in_pdf[o] = True
                        
    present = [o for o, f in found_in_pdf.items() if f]
    absent = [o for o, f in found_in_pdf.items() if not f]
    
    print(f"\nResults:")
    print(f"Found IN PDF: {len(present)}")
    print(f"NOT in PDF: {len(absent)}")
    
    with open('c:/Movies/quotation-ai/quotation-ai/backend/orphan_verification.txt', 'w', encoding='utf-8') as f:
        f.write(f"Orphans ACTUALLY IN PDF (Extraction missed them!): {len(present)}\n")
        for o in present:
            f.write(f" - {o}\n")
            
        f.write(f"\nOrphans TRULY NOT IN PDF: {len(absent)}\n")
        for o in absent:
            f.write(f" - {o}\n")

if __name__ == '__main__':
    main()
