import os
import urllib.parse
from pdf_reader import extract_content

def main():
    pdf_path = r"c:\Movies\quotation-ai\quotation-ai\backend\uploads\Kohler_PriceBook (June'26).pdf"
    image_dir = r"c:\Movies\quotation-ai\quotation-ai\backend\static\images\Kohler"
    
    print("Extracting items from PDF...")
    items = extract_content(pdf_path)
    
    # Pre-compute all available files in the directory for fast lookup (case-insensitive)
    existing_files = {f.lower() for f in os.listdir(image_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))}
    
    missing_count = 0
    missing_items = []
    
    for item in items:
        # A product might have multiple image URLs defined if extracted correctly, 
        # or we might just check its search_code / base_code directly.
        code = str(item.get('search_code', '')).strip()
        if not code:
            code = str(item.get('base_code', '')).strip()
            
        found = False
        
        # 1. Check if any image URL specified in the item physically exists
        for img_url in item.get('images', []):
            filename = urllib.parse.urlparse(img_url).path.split('/')[-1]
            if filename.lower() in existing_files:
                found = True
                break
                
        # 2. Check if a file named exactly {code}.png or {code}.jpg exists
        if not found and code:
            if f"{code.lower()}.png" in existing_files or f"{code.lower()}.jpg" in existing_files:
                found = True
                
        if not found:
            missing_count += 1
            missing_items.append(code)
            
    print(f"Total items extracted: {len(items)}")
    print(f"Total items MISSING images: {missing_count}")
    
    with open("c:/Movies/quotation-ai/quotation-ai/backend/missing_1473_analysis.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(missing_items))

if __name__ == '__main__':
    main()
