import fitz
import re
import json

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
aquant_codes = {i['search_code'] for i in d.get('stored_items',[]) if i.get('brand') == 'Aquant'}
aquant_bases = {c.split()[0] for c in aquant_codes}

doc = fitz.open('c:/Movies/quotation-ai/quotation-ai/backend/uploads/Aquant Price List Vol 15. Feb 2026_Searchable.pdf')

code_descs = {}

IGNORE_LINES = ["FAUCETS", "SHOWERING", "SYSTEMS", "SPECIAL FINISHES", "Main Menu", "Aquant"]

for page_num in range(doc.page_count):
    page = doc[page_num]
    blocks = page.get_text('blocks')
    
    current_desc = []
    
    for b in blocks:
        text = b[4].strip()
        text = re.sub(r'[\u200b-\u200f\u2028\u2029]', '', text)
        text = text.replace('\x03', ' ')
        
        codes_in_block = []
        for line in text.split('\n'):
            line = line.strip()
            match = re.match(r'^(\d{4}(?:-\d+)?(?:\s+[A-Z]{2})?)', line)
            if match:
                c = match.group(1).strip()
                if c in aquant_codes or c.split()[0] in aquant_bases:
                    codes_in_block.append(c)
        
        if codes_in_block:
            clean_d = []
            for d_line in current_desc:
                if d_line.isdigit(): continue
                if any(ign in d_line for ign in IGNORE_LINES): continue
                if 'Size' in d_line and 'MRP' in d_line:
                    size_part = d_line.split('l MRP')[0].strip()
                    clean_d.append(size_part)
                elif 'MRP' not in d_line:
                    clean_d.append(d_line)
                    
            joined_desc = " ".join(clean_d).strip()
            if joined_desc:
                for c in codes_in_block:
                    code_descs[c] = joined_desc
        else:
            if text and not text.isdigit() and 'MRP' not in text:
                lines = text.split('\n')
                new_desc_lines = [l for l in lines if not l.isdigit() and not any(ign in l for ign in IGNORE_LINES)]
                if new_desc_lines:
                    current_desc = new_desc_lines

for code in ['1313 CP', '1314 CP', '1424 CP', '2642 CP', '1110 MM']:
    base = code.split()[0]
    matched = next((v for k,v in code_descs.items() if base in k), "NOT FOUND")
    print(f"{code} -> {matched}")
