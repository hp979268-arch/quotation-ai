import json
import fitz
import re

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

aquant_items = [i for i in d.get('stored_items',[]) if i.get('brand') == 'Aquant']

doc = fitz.open('c:/Movies/quotation-ai/quotation-ai/backend/uploads/Aquant Price List Vol 15. Feb 2026_Searchable.pdf')

# Extract ALL blocks that have a 4-digit code + MRP  
pdf_prices = {}

for page_num in range(doc.page_count):
    page = doc[page_num]
    blocks = page.get_text('blocks')
    
    for b in blocks:
        text = b[4].strip()
        text = text.replace('\x03', ' ')
        text = re.sub(r'[\u200b-\u200f\u2028\u2029]', '', text)
        
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            # Match a line like "2637 CP" or "1313 CP"
            code_match = re.match(r'^(\d{4}(?:-\d+)?)\s+([A-Z]{2,3})\s*$', line)
            if code_match:
                code = code_match.group(1) + ' ' + code_match.group(2)
                # Look for MRP in next line or same block
                rest = '\n'.join(lines[i+1:i+3])
                mrp_match = re.search(r'MRP\s*:?\s*`\s*([\d,]+)/-', rest, re.IGNORECASE)
                if mrp_match:
                    price = mrp_match.group(1).replace(',', '')
                    pdf_prices[code] = price

print(f'Prices extracted from PDF: {len(pdf_prices)}')

# Show sample
for k, v in list(pdf_prices.items())[:15]:
    print(f'  {k} -> {v}')

# Compare with DB
print('\n--- Mismatches ---')
mismatches = []
for item in aquant_items:
    code = item['search_code']
    db_price = str(item.get('price', '0')).replace(',','').strip()
    
    if code in pdf_prices:
        pdf_price = pdf_prices[code]
        if db_price != pdf_price:
            mismatches.append({'code': code, 'db_price': db_price, 'pdf_price': pdf_price})

print(f'Mismatches: {len(mismatches)}')
for m in mismatches[:30]:
    print(f"  {m['code']}: DB={m['db_price']} | PDF={m['pdf_price']}")
