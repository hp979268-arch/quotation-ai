import json
import fitz
import re
from app_paths import resolve_data_dir

def fix_all_aquant_variants():
    INDEX_FILE = 'backend/search_index_v2.json'
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        db = json.load(f)

    # Known special finishes
    special_finishes = {"BRG", "BG", "GG", "MB", "RG", "CB", "SM", "BM", "RGB", "RGW", "GW", "MW", "J"}
    
    # Find all Aquant products with special finishes
    target_items = []
    for i in db['stored_items']:
        if i.get('brand') == 'Aquant':
            search_code = i.get('search_code', '')
            parts = search_code.split(' ')
            if len(parts) > 1:
                variant = parts[1]
                if variant in special_finishes or any(x in variant for x in special_finishes):
                    # It's a special variant!
                    target_items.append(i)

    print(f"Found {len(target_items)} Aquant variants to re-verify prices for.")

    doc = fitz.open(r"backend/uploads/Aquant Price List Vol 15. Feb 2026_Searchable.pdf")
    blocks = []
    for p in doc:
        for b in p.get_text('blocks'):
            clean_text = b[4].replace('\x03', ' ').strip()
            blocks.append(clean_text)
            
    fixes = {}
    changed = 0
    
    for item in target_items:
        code = item['search_code']
        base_code = item.get('base_code', code.split(' ')[0])
        current_price = str(item.get('price', '0'))
        
        found_price = None
        all_window_mrps = []
        for i, block_text in enumerate(blocks):
            if code in block_text or f"{base_code} {code.split(' ')[-1]}" in block_text:
                for j in range(i, max(-1, i-7), -1):
                    prev_block = blocks[j]
                    mrps = re.findall(r'(?:MRP|PRICE)\s*[:-]?\s*[`₹]?\s*([\d,]+)', prev_block, re.IGNORECASE)
                    if mrps:
                        vals = [int(m.replace(',', '')) for m in mrps]
                        all_window_mrps.extend([v for v in vals if v > 1000])
                if all_window_mrps:
                    found_price = str(max(all_window_mrps))
                    break
                    
        if found_price and found_price != current_price:
            fixes[code] = found_price
            item['price'] = found_price
            print(f"Fixed {code}: {current_price} -> {found_price}")
            changed += 1
            
    if changed > 0:
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        print(f"Applied {changed} fixes. Updating MongoDB...")
        
        # Also sync directly to old mongo database to update the live site
        try:
            import pymongo
            client = pymongo.MongoClient("mongodb+srv://admin:admin123@cluster0.5dxlcpj.mongodb.net/?appName=Cluster0")
            mongo_db = client["quotation_ai"]
            doc_obj = dict(db)
            doc_obj["_id"] = "global"
            mongo_db["search_index"].replace_one({"_id": "global"}, doc_obj, upsert=True)
            mongo_db["search_index_v2"].replace_one({"_id": "global"}, doc_obj, upsert=True)
            print("Successfully pushed latest search index to MongoDB!")
        except Exception as e:
            print(f"Failed to sync mongo: {e}")
    else:
        print("No changes were needed.")

if __name__ == '__main__':
    fix_all_aquant_variants()
