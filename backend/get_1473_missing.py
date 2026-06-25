import json
import os
import re

def main():
    items = json.load(open('c:/Movies/quotation-ai/quotation-ai/backend/1473_items_dump.json', 'r', encoding='utf-8'))
    img_dir = 'c:/Movies/quotation-ai/quotation-ai/backend/static/images/Kohler'
    exist = {f.lower() for f in os.listdir(img_dir) if f.lower().endswith(('.png', '.jpg'))}
    
    missing = 0
    missing_items = []
    
    for i in items:
        name = str(i.get('name', ''))
        codes = re.findall(r'\b(?:K-|EX)[A-Z0-9-]+\b', name)
        
        # Some items don't have K- or EX-, try to grab whatever is in parenthesis
        if not codes:
            m = re.search(r'\((.*?)\)$', name)
            if m:
                code = m.group(1).strip()
            else:
                code = name.strip()
        else:
            code = codes[-1] # Usually the code is at the end of the name
            
        code = code.lower().replace('/', '-') # handle weird characters just in case
        
        if f"{code}.png" not in exist and f"{code}.jpg" not in exist:
            missing += 1
            missing_items.append(name)
            
    print(f"Total missing out of 1473: {missing}")

if __name__ == '__main__':
    main()
