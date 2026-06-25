import json

def main():
    path = r'c:\Movies\quotation-ai\quotation-ai\backend\search_index_v2.json'
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    updated = 0
    for i in data.get('stored_items', []):
        if i.get('brand', '').lower() == 'kohler' and i.get('images'):
            new_imgs = []
            for img in i['images']:
                if '?v=' in img:
                    img = img.split('?v=')[0] + '?v=26'
                else:
                    img = img + '?v=26'
                new_imgs.append(img)
            i['images'] = new_imgs
            updated += 1
            
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        
    print(f"Updated cache buster to ?v=26 for {updated} Kohler items.")

if __name__ == '__main__':
    main()
