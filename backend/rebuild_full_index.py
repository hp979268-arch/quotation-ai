import search_engine
import json

print("Loading index...")
search_engine.load_index()

print("Reading raw JSON...")
with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data.get('stored_items', [])
print(f"Loaded {len(items)} items for rebuild.")

# Clear existing indices
search_engine.stored_items = []
search_engine.keyword_index = {}
search_engine.vector_index = None

print("Rebuilding keyword index...")
search_engine.add_to_index(None, items)
print("Index rebuilt and saved successfully!")
