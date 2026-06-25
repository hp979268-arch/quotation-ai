"""
Connect to live MongoDB and compare with local search_index_v2.json
Report any mismatches in price or images.
"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import json

load_dotenv('backend/.env')
mongo_uri = os.getenv('MONGO_URI')

if not mongo_uri:
    print("MONGO_URI not found!")
    exit(1)

# Connect to DB
client = MongoClient(mongo_uri)
db = client['quotation_ai']  # Guessing db name, will check
# Let's list dbs first
dbs = client.list_database_names()
print(f"Databases: {dbs}")

db_name = 'test' if 'test' in dbs else dbs[0]
if 'quotation_ai' in dbs: db_name = 'quotation_ai'
if 'production' in dbs: db_name = 'production'

db = client[db_name]
collections = db.list_collection_names()
print(f"Collections in {db_name}: {collections}")

col_name = 'products'
if 'search_index' in collections: col_name = 'search_index'
if 'stored_items' in collections: col_name = 'stored_items'

col = db[col_name]
live_docs = list(col.find({}))
print(f"Loaded {len(live_docs)} records from live DB.")

# Load local
with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    local_data = json.load(f)
local_items = local_data.get('stored_items', [])

local_map = {}
for item in local_items:
    if isinstance(item, dict) and item.get('search_code'):
        local_map[item['search_code']] = item

mismatches = []
for doc in live_docs:
    sc = doc.get('search_code')
    if not sc: continue
    
    local = local_map.get(sc)
    if not local:
        mismatches.append(f"Product {sc} exists in Live but missing locally.")
        continue
        
    # Check Price
    lp_str = str(local.get('price', ''))
    dp_str = str(doc.get('price', ''))
    if lp_str != dp_str:
        mismatches.append(f"PRICE MISMATCH: {sc} -> Live: {dp_str}, Local: {lp_str}")
        
    # Check Images / Colors
    # Just checking first image to see if there's a difference
    limages = local.get('images', [])
    dimages = doc.get('images', [])
    limg = limages[0] if limages else ""
    dimg = dimages[0] if dimages else ""
    
    # Ignore the ?v= version tag differences
    limg_clean = limg.split('?')[0]
    dimg_clean = dimg.split('?')[0]
    
    if limg_clean != dimg_clean:
        mismatches.append(f"IMAGE MISMATCH: {sc} -> Live: {dimg_clean}, Local: {limg_clean}")

print(f"\nFound {len(mismatches)} mismatches.")
for m in mismatches[:20]:
    print(m)

if not mismatches:
    print("Live DB exactly matches local index for all compared items!")
