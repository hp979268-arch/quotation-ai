"""
Directly push search_index_v2.json to MongoDB.
"""
import json
import pymongo
import os

MONGO_URI = "mongodb+srv://hp979268_db_user:PQo6mPT7DugIoi4f@cluster0.wkcfszp.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
INDEX_PATH = r"c:\Movies\quotation-ai\quotation-ai\backend\search_index_v2.json"

print("Connecting to MongoDB...")
try:
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    client.admin.command('ping')
    print("Connected!")
except Exception as e:
    print(f"Connection FAILED: {e}")
    exit(1)

db = client["quotation_ai"]

print(f"Loading index from: {INDEX_PATH}")
with open(INDEX_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

items_count = len(data.get('stored_items', []))
print(f"Loaded {items_count} items. Uploading to MongoDB...")

doc = dict(data)
doc["_id"] = "global"

db["search_index_v3"].replace_one({"_id": "global"}, doc, upsert=True)
print(f"SUCCESS: {items_count} items saved to MongoDB search_index_v3!")

# Verify
count = db["search_index_v3"].count_documents({})
print(f"Verification: {count} documents in collection.")
