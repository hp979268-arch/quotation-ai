import fitz
import re
import json

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

aquant_items = [i for i in data.get('stored_items',[]) if i.get('brand') == 'Aquant']
aquant_codes = {i['search_code'] for i in aquant_items}
aquant_bases = {c.split()[0] for c in aquant_codes}

doc = fitz.open('c:/Movies/quotation-ai/quotation-ai/backend/uploads/Aquant Price List Vol 15. Feb 2026_Searchable.pdf')

code_descs = {}
IGNORE_LINES = ["FAUCETS", "SHOWERING", "SYSTEMS", "SPECIAL FINISHES", "Main Menu", "Aquant", "SERIES", "WALL HUNG", "WASH BASINS", "TABLE MOUNTED", "IN", "AND", "&", "COLLECTION", "PRICE", "LIST", "MRP", "mrp", "Size"]

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
                # Exact matches or pure uppercase categories
                if d_line in IGNORE_LINES or d_line.isupper() and len(d_line.split()) < 3: continue
                if 'Size' in d_line and 'MRP' in d_line:
                    size_part = d_line.split('l MRP')[0].strip()
                    if size_part: clean_d.append(size_part)
                elif 'MRP' not in d_line:
                    clean_d.append(d_line)
                    
            joined_desc = " ".join(clean_d).strip()
            if joined_desc:
                for c in codes_in_block:
                    code_descs[c] = joined_desc
                    
        else:
            if text and not text.isdigit():
                lines = text.split('\n')
                new_desc_lines = []
                for l in lines:
                    l = l.strip()
                    if not l: continue
                    if l.isdigit(): continue
                    if l in IGNORE_LINES or (l.isupper() and len(l.split()) < 3): continue
                    
                    if 'l MRP' in l:
                        p = l.split('l MRP')[0].strip()
                        if p: new_desc_lines.append(p)
                    elif 'MRP :' in l and len(l) < 25:
                        continue
                    else:
                        new_desc_lines.append(l)
                        
                if new_desc_lines:
                    current_desc = new_desc_lines

print(f"Extracted generic descriptions for {len(code_descs)} codes.")

updated_count = 0
for item in data.get("stored_items", []):
    if item.get("brand") == "Aquant":
        code = item["search_code"]
        
        base = code.split()[0]
        desc = None
        if code in code_descs:
            desc = code_descs[code]
        else:
            for k, v in code_descs.items():
                if k.split()[0] == base:
                    desc = v
                    break
                    
        # Fallback to name if description not extracted but name exists and is detailed
        if not desc:
            name_parts = item["name"].split(' - ', 1)
            if len(name_parts) > 1 and len(name_parts[1]) > 5:
                desc = name_parts[1]

        if desc:
            lines = item['text'].split('\n')
            
            # Ensure it's not duplicating description
            if len(lines) <= 2 or desc not in item['text']:
                # The text usually starts with the code itself. We will prepend the description just like Aquant
                new_text = f"{code} - {desc}\n{desc}\nMRP : ₹ {item['price']}/-"
                item["text"] = new_text
                
                new_name = f"{code} - {desc}"
                if new_name != item["name"]:
                    item["name"] = new_name
                    
                updated_count += 1

print(f"Updated {updated_count} Aquant items in JSON.")

with open("c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Done!")
