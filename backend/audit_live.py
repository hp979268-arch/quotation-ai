import json
import pymongo
from pymongo import MongoClient

OLD_URI = "mongodb+srv://admin:admin123@cluster0.5dxlcpj.mongodb.net/?appName=Cluster0"
INDEX_FILE = "backend/search_index_v2.json"

def main():
    print("Loading local JSON catalog (Master Data)...")
    with open(INDEX_FILE, "r", encoding="utf-8-sig") as f:
        master_data = json.load(f)
        
    master_items = {}
    for item in master_data.get("stored_items", []):
        code = str(item.get("search_code") or item.get("base_code") or "").strip().upper()
        if code:
            master_items[code] = item

    print("Connecting to Live MongoDB Database...")
    try:
        # bypass SSL to avoid the handshake error locally
        client = MongoClient(OLD_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=10000)
        db = client["quotation_ai"]
        live_doc = db["search_index"].find_one({"_id": "global"})
        if not live_doc:
            print("Could not find 'global' search_index in MongoDB.")
            return
            
        live_items = live_doc.get("stored_items", [])
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return

    print(f"Comparing {len(live_items)} live items against {len(master_items)} master items...")
    
    wrong_price_count = 0
    wrong_image_count = 0
    wrong_desc_count = 0
    missing_in_live = 0
    
    price_errors = []
    image_errors = []
    
    for live_item in live_items:
        code = str(live_item.get("search_code") or live_item.get("base_code") or "").strip().upper()
        if not code:
            continue
            
        master_item = master_items.get(code)
        if not master_item:
            # Maybe it's missing in master? We only care if live is wrong compared to master
            continue
            
        # Price Check
        live_price = str(live_item.get("price") or "0").strip()
        master_price = str(master_item.get("price") or "0").strip()
        if live_price != master_price:
            wrong_price_count += 1
            if len(price_errors) < 10:
                price_errors.append(f"[{code}] Live: {live_price} | Master: {master_price}")
                
        # Image Check
        live_images = live_item.get("images") or []
        master_images = master_item.get("images") or []
        # comparing lists or at least lengths
        if live_images != master_images:
            wrong_image_count += 1
            if len(image_errors) < 5:
                image_errors.append(f"[{code}] Live: {len(live_images)} imgs | Master: {len(master_images)} imgs")
                
        # Description check
        live_text = str(live_item.get("text", "")).strip()
        master_text = str(master_item.get("text", "")).strip()
        if live_text != master_text:
            wrong_desc_count += 1
            
    # Check missing in live
    live_codes = {str(x.get("search_code") or x.get("base_code") or "").strip().upper() for x in live_items}
    for code in master_items.keys():
        if code not in live_codes:
            missing_in_live += 1
            
    print("\n--- AUDIT REPORT ---")
    print(f"Wrong Prices: {wrong_price_count}")
    print(f"Wrong Images: {wrong_image_count}")
    print(f"Different Descriptions: {wrong_desc_count}")
    print(f"Items completely missing from Live DB: {missing_in_live}")
    
    if price_errors:
        print("\nExamples of Price Errors:")
        for err in price_errors:
            print("  " + err)
            
    if image_errors:
        print("\nExamples of Image Mismatches:")
        for err in image_errors:
            print("  " + err)
            
    print("\nAudit Complete.")

if __name__ == "__main__":
    main()
