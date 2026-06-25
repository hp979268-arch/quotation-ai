import json
with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', encoding='utf-8') as f:
    data = json.load(f)

root_images = set()
total_images = 0

for item in data.get('stored_items', []):
    for img in item.get('images', []):
        total_images += 1
        path = img.split('?')[0] # remove ?v=x
        # path is like /static/images/Kohler/xxx.png or /static/images/xxx.png
        # if there are only 3 slashes, it's directly in /static/images/
        if str(path).startswith('/static/images/') and path.count('/') == 3:
            root_images.add(path)

print(f'Total image paths in DB: {total_images}')
print(f'Images from root static/images/: {len(root_images)}')
for r in list(root_images)[:10]:
    print(" -", r)
