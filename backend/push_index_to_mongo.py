"""
Push updated search_index_v2.json (with v=30 cache-busted image URLs)
to MongoDB so the live Render backend loads the fresh data.
"""
import sys, os, json
sys.path.insert(0, r"c:\Movies\quotation-ai\quotation-ai\backend")
from dotenv import load_dotenv
# Load .env and also set MONGO_URI explicitly from the file
load_dotenv(r"c:\Movies\quotation-ai\quotation-ai\backend\.env", override=True)
print("MONGO_URI present:", bool(os.environ.get("MONGO_URI")))

import mongodb

if not mongodb.is_enabled():
    print("ERROR: MongoDB not enabled. Check MONGO_URI env var.")
    sys.exit(1)

INDEX_PATH = r"c:\Movies\quotation-ai\quotation-ai\backend\search_index_v2.json"
print(f"Loading index from: {INDEX_PATH}")
with open(INDEX_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Loaded {len(data.get('stored_items', []))} items.")
print("Pushing to MongoDB...")
mongodb.save_search_index(data)
print("SUCCESS: MongoDB search index updated!")
