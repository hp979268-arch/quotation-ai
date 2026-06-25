import json
import os
import urllib.parse

def main():
    index_path = 'c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json'
    image_dir = 'c:/Movies/quotation-ai/quotation-ai/backend/static/images/Kohler'
    
    with open(index_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    kohler_items = [i for i in data.get('stored_items', []) if i.get('brand', '').lower() == 'kohler']
    
    existing_files = {f.lower() for f in os.listdir(image_dir) if f.lower().endswith('.png') or f.lower().endswith('.jpg')}
    
    missing = []
    missing_data = []
    
    for item in kohler_items:
        images = item.get('images', [])
        found_image = False
        
        for img_url in images:
            filename = urllib.parse.urlparse(img_url).path.split('/')[-1].lower()
            if filename in existing_files:
                found_image = True
                break
                
        # Also check if a file exactly matching the search_code exists
        search_code = str(item.get('search_code', '')).strip()
        if not found_image and search_code:
            code_lower = search_code.lower()
            if f"{code_lower}.png" in existing_files or f"{code_lower}.jpg" in existing_files:
                found_image = True
                
        if not found_image:
            missing.append(f"- **{search_code}**: {item.get('name', 'N/A')}")
            missing_data.append({
                "code": search_code,
                "name": item.get('name', 'N/A'),
                "page": item.get('page', 'N/A')
            })
            
    # Sort for readability
    missing.sort()
    
    # Write report
    report_path = 'c:/Movies/quotation-ai/quotation-ai/backend/missing_images_report.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# Kohler Missing Images Report\n\n")
        f.write(f"- Total Kohler Products in Index: {len(kohler_items)}\n")
        f.write(f"- Total Products Missing Images: {len(missing)}\n\n")
        f.write("## Missing Products List\n\n")
        f.write("\n".join(missing))
        
    print(f"Total Kohler items: {len(kohler_items)}")
    print(f"Missing images: {len(missing)}")

if __name__ == '__main__':
    main()
