import json

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

updated = 0
for item in data.get('stored_items', []):
    code = item.get('search_code', '')
    if code.startswith('30006-30007 '):
        # Ensure both 30006 and 30007 appear in text for search indexing
        existing_text = item.get('text', '')
        if '30006' not in existing_text or '30007' not in existing_text:
            # Prepend both codes as searchable aliases
            item['text'] = f"30006 30007 {code}\n{existing_text}"
        # Also set full_code explicitly so indexer picks it up
        item['full_code'] = code
        updated += 1
        print(f"Updated: {code}")

print(f"\nTotal updated: {updated}")

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Saved!")
