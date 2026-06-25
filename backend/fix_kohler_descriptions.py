import json
import fitz
import re

print("Loading search index...")
with open("c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json", "r", encoding="utf-8") as f:
    data = json.load(f)

kohler_items = [item for item in data.get("stored_items", []) if item.get("brand") == "Kohler"]
kohler_codes = {item["search_code"] for item in kohler_items}

print(f"Found {len(kohler_codes)} Kohler items.")

doc = fitz.open("c:/Movies/quotation-ai/quotation-ai/backend/uploads/Kohler_PriceBook (June'26).pdf")

code_descriptions = {}
IGNORE_TEXTS = {"MODEL", "DESCRIPTION", "CODE", "MRP", "Main Menu"}

for page_num in range(doc.page_count):
    page = doc[page_num]
    blocks = page.get_text("blocks")
    
    accumulated_text = []
    
    for b in blocks:
        text = b[4].strip()
        text = re.sub(r'[\u200b-\u200f\u2028\u2029]', '', text)
        text = text.replace('\x03', ' ')
        
        found_codes = []
        # Match only exact whole word codes
        potential_codes = re.findall(r'\bK-[A-Z0-9\-]+\b', text)
        # Avoid duplicate codes in the same block if it mentions it multiple times
        for pc in dict.fromkeys(potential_codes):
            if pc in kohler_codes:
                found_codes.append(pc)
        
        if found_codes:
            for code in found_codes:
                desc = []
                # 1. Add accumulated text from previous blocks
                for line in accumulated_text:
                    if not line: continue
                    if line.isdigit(): continue
                    if any(ign == line.strip() for ign in IGNORE_TEXTS): continue
                    if "Must order" in line: continue
                    if "incl of all taxes" in line: continue
                    if "Main Menu" in line: continue
                    if re.match(r'^`?\s*[\d,]+\.\d+$', line): continue
                    desc.append(line.replace('\n', ' '))
                
                # 2. Add text from the current block BEFORE the code
                parts = text.split(code)
                text_before = parts[0].strip()
                for line in text_before.split('\n'):
                    line = line.strip()
                    if not line: continue
                    if line.isdigit(): continue
                    if any(ign == line for ign in IGNORE_TEXTS): continue
                    if "Must order" in line: continue
                    if "incl of all taxes" in line: continue
                    if "Main Menu" in line: continue
                    if re.match(r'^`?\s*[\d,]+\.\d+$', line): continue
                    desc.append(line)
                
                clean_desc = []
                for d_line in desc:
                    d_line = d_line.strip(' \n|')
                    if d_line and d_line not in clean_desc:
                        clean_desc.append(d_line)
                
                if clean_desc:
                    code_descriptions[code] = "\n".join(clean_desc)
                
            accumulated_text = []
            # What about text AFTER the code? We can ignore it because it's usually MRP or price.
            # But wait, what if the block had multiple codes?
            # It's rare, but we handle it simply above.
        else:
            if text and not text.isdigit() and "MRP" not in text and "incl of all taxes" not in text:
                accumulated_text.append(text)

print(f"Extracted descriptions for {len(code_descriptions)} items.")

updated_count = 0
for item in data.get("stored_items", []):
    if item.get("brand") == "Kohler":
        code = item["search_code"]
        if code in code_descriptions:
            desc = code_descriptions[code]
            if desc:
                lines = desc.split('\n')
                name_line = lines[0]
                if len(name_line) < 5 and len(lines) > 1:
                    name_line = lines[0] + " " + lines[1]
                
                new_text = f"{code} - {desc}\nMRP : ₹ {item['price']}/-"
                new_name = f"{code} - {name_line}"
                
                item["name"] = new_name
                item["text"] = new_text
                updated_count += 1

print(f"Updated {updated_count} Kohler items in JSON.")

with open("c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Done!")
