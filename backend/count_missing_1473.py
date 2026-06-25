import os
from pdf_reader import extract_content, normalize_kohler_code

def main():
    pdf_path = r"c:\Movies\quotation-ai\quotation-ai\backend\uploads\Kohler_PriceBook (June'26).pdf"
    image_dir = r"c:\Movies\quotation-ai\quotation-ai\backend\static\images\Kohler"
    
    # Extract the raw 1473 items
    items = extract_content(pdf_path)
    exist = {f.lower() for f in os.listdir(image_dir) if f.lower().endswith(('.png', '.jpg'))}
    
    missing_items_count = 0
    missing_variants_list = []
    
    # We will check if the base code or ANY of its finish variants has an image.
    # To be thorough, we will extract the exact variant codes.
    for i in items:
        # pdf_reader actually processes these items into search_index. 
        # But here we just look at the raw item string to find the code
        # A better way is to look at the name, usually "Desc (CODE)"
        name = str(i.get('name', ''))
        code_str = ""
        if '(' in name and ')' in name:
            code_str = name[name.rfind('(')+1:name.rfind(')')].strip()
        else:
            code_str = name.split()[0] if name else ""
            
        base_code = normalize_kohler_code(code_str)
        
        # Check if base_code has an image
        has_image = False
        if f"{base_code.lower()}.png" in exist or f"{base_code.lower()}.jpg" in exist:
            has_image = True
            
        # If not, check if it's one of the known missing ones
        if not has_image:
            missing_items_count += 1
            missing_variants_list.append(base_code)
            
    print(f"Total extracted from PDF: {len(items)}")
    print(f"Total Items MISSING Images: {missing_items_count}")
    
    with open('c:/Movies/quotation-ai/quotation-ai/backend/missing_from_1473.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(missing_variants_list))

if __name__ == '__main__':
    main()
