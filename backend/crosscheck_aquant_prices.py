import fitz
import re
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

aquant_items = [i for i in data.get('stored_items', []) if i.get('brand') == 'Aquant']

doc = fitz.open('c:/Movies/quotation-ai/quotation-ai/backend/uploads/Aquant Price List Vol 15. Feb 2026_Searchable.pdf')

# Step 1: Extract ALL prices from PDF per exact code
pdf_prices = {}  # exact_code -> price_int

for page_num in range(doc.page_count):
    page = doc[page_num]
    blocks = page.get_text('blocks')

    for b in blocks:
        raw = b[4].replace('\x03', ' ')
        raw = re.sub(r'[\u200b-\u200f\u2028\u2029]', '', raw)
        text = raw.strip()

        # Pattern 1: Code on first line, MRP on same or next line(s)
        # e.g. "2638 AB\nThermostatic Shower Column\n...MRP : ` 1,71,500/-"
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            # Match code like "2638 AB" or "1313 CP" or "1424-200 BRG" or "1500 MM"
            code_match = re.match(
                r'^(\d{4}(?:-\d+)?)\s+([A-Z]{1,3})\s*$', line
            )
            if code_match:
                code = code_match.group(1) + ' ' + code_match.group(2)
                # Search for MRP in remaining lines of same block
                rest = '\n'.join(lines[i:i+8])
                mrp_match = re.search(r'MRP\s*:?\s*`\s*([\d,]+)/-', rest, re.IGNORECASE)
                if mrp_match:
                    price = int(mrp_match.group(1).replace(',', ''))
                    pdf_prices[code] = price

        # Pattern 2: Inline "2638 AB\nMRP : ` 1,71,500/-" (code + MRP in same block first lines)
        first_line = lines[0].strip() if lines else ''
        code_match2 = re.match(r'^(\d{4}(?:-\d+)?)\s+([A-Z]{1,3})\s*$', first_line)
        if code_match2:
            code = code_match2.group(1) + ' ' + code_match2.group(2)
            block_text = '\n'.join(lines[:6])
            mrp_match2 = re.search(r'MRP\s*:?\s*`\s*([\d,]+)/-', block_text, re.IGNORECASE)
            if mrp_match2:
                price = int(mrp_match2.group(1).replace(',', ''))
                pdf_prices[code] = price

print(f"Prices extracted from PDF: {len(pdf_prices)}")

# Step 2: Cross-check every Aquant item
print("\n{'=':=<70}")
print(f"{'CODE':<20} {'DB PRICE':>12} {'PDF PRICE':>12} {'STATUS':>10}")
print(f"{'':=<20} {'':=<12} {'':=<12} {'':=<10}")

mismatches = []
not_found = []
ok_count = 0

for item in aquant_items:
    code = item['search_code']
    db_price = int(float(str(item.get('price', '0')).replace(',', '').strip() or 0))

    if code in pdf_prices:
        pdf_price = pdf_prices[code]
        if db_price != pdf_price:
            status = "MISMATCH ❌"
            mismatches.append({
                'code': code,
                'db_price': db_price,
                'pdf_price': pdf_price
            })
            print(f"{code:<20} {db_price:>12,} {pdf_price:>12,} {status}")
        else:
            ok_count += 1
    else:
        not_found.append(code)

print(f"\n{'=':=<70}")
print(f"✅ Correct prices:         {ok_count}")
print(f"❌ Mismatches found:       {len(mismatches)}")
print(f"⚠️  Not in PDF (no check): {len(not_found)}")

if not_found:
    print(f"\nSample not found in PDF: {not_found[:10]}")
