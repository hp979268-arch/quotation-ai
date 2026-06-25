import json
import re
import os
import search_engine

def get_search_code(name):
    codes = re.findall(r'\b(?:K-|EX)[A-Z0-9-]+\b', name)
    if not codes:
        m = re.search(r'\((.*?)\)$', name)
        code = m.group(1).strip().upper() if m else name.strip().upper()
    else:
        code = codes[-1].upper()
    return code.replace('/', '-')

def get_base_code(search_code):
    base_code = search_code
    if '-' in search_code:
        parts = search_code.split('-')
        if len(parts) >= 2 and any(char.isdigit() for char in parts[1]):
            base_code = "-".join(parts[:-1])
    return base_code

def main():
    index_path = r'c:\Movies\quotation-ai\quotation-ai\backend\search_index_v2.json'
    dump_path = r'c:\Movies\quotation-ai\quotation-ai\backend\1473_items_dump.json'
    
    # 1. Load existing index and filter OUT Kohler items
    with open(index_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    aquant_items = [i for i in data.get('stored_items', []) if i.get('brand', '').lower() == 'aquant']
    print(f"Kept {len(aquant_items)} Aquant items.")
    
    # 2. Load pure June 1473 items dump
    with open(dump_path, 'r', encoding='utf-8') as f:
        raw_kohler = json.load(f)
        
    print(f"Processing {len(raw_kohler)} pure June Kohler items...")
    
    new_kohler_items = []
    for raw_item in raw_kohler:
        name = raw_item.get('name', '')
        search_code = get_search_code(name)
        base_code = get_base_code(search_code)
        
        new_item = {
            "text": raw_item.get("text", ""),
            "name": name,
            "price": str(raw_item.get("price", "")).replace(',', '').strip(),
            "images": [f"/static/images/Kohler/{search_code}.png?v=36"],
            "brand": "Kohler",
            "category": raw_item.get("category", ""),
            "search_code": search_code,
            "base_code": base_code,
            "source": "Kohler_PriceBook (June'26)"
        }
        new_kohler_items.append(new_item)
        
    print(f"Prepared {len(new_kohler_items)} clean Kohler items.")
    
    # 3. Rebuild search engine
    search_engine.stored_items = []
    search_engine.keyword_index = {}
    search_engine.vector_index = None
    
    all_items = aquant_items + new_kohler_items
    search_engine.add_to_index(None, all_items)
    search_engine.save_index()
    
    print(f"Deep clean complete. Saved index with {len(all_items)} total items.")

if __name__ == '__main__':
    main()
