import json

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# The 7 combo images now in main folder:
# "30006-30007 CP.png", "30006-30007 BG.png", "30006-30007 BRG.png",
# "30006-30007 G.png",  "30006-30007 GG.png", "30006-30007 MB.png", "30006-30007 RG.png"

# Map finish -> filename
finish_to_file = {
    'CP':  '30006-30007 CP.png',
    'BG':  '30006-30007 BG.png',
    'BRG': '30006-30007 BRG.png',
    'G':   '30006-30007 G.png',
    'GG':  '30006-30007 GG.png',
    'MB':  '30006-30007 MB.png',
    'RG':  '30006-30007 RG.png',
}

updated = 0
for item in data.get('stored_items', []):
    code = item.get('search_code', '')
    # Match 30006 XX or 30007 XX
    if code.startswith('30006 ') or code.startswith('30007 '):
        parts = code.split()
        if len(parts) == 2:
            finish = parts[1]
            if finish in finish_to_file:
                new_img = f"/static/images/Aquant/{finish_to_file[finish]}?v=8"
                item['images'] = [new_img]
                print(f"  {code} -> {new_img}")
                updated += 1

print(f"\nTotal updated: {updated}")

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Saved!")
