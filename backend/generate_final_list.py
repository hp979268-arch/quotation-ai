import json
import os
import re

def main():
    items = json.load(open('c:/Movies/quotation-ai/quotation-ai/backend/1473_items_dump.json', 'r', encoding='utf-8'))
    img_dir = 'c:/Movies/quotation-ai/quotation-ai/backend/static/images/Kohler'
    exist = {f.lower() for f in os.listdir(img_dir) if f.lower().endswith(('.png', '.jpg'))}
    
    with open('c:/Movies/quotation-ai/quotation-ai/backend/updated_images.txt', 'r', encoding='utf-8') as f:
        updated_codes = {line.strip().lower() for line in f if line.strip()}
        
    missing_list = set()
    updated_list = set()
    
    for i in items:
        name = str(i.get('name', ''))
        codes = re.findall(r'\b(?:K-|EX)[A-Z0-9-]+\b', name)
        
        if not codes:
            m = re.search(r'\((.*?)\)$', name)
            if m:
                code = m.group(1).strip()
            else:
                code = name.strip()
        else:
            code = codes[-1]
            
        code_clean = code.lower().replace('/', '-')
        
        if code_clean in updated_codes:
            updated_list.add(code)
            continue
            
        if f"{code_clean}.png" not in exist and f"{code_clean}.jpg" not in exist:
            missing_list.add(code)
            
    final_list = sorted(list(missing_list.union({c.upper() for c in updated_list})))
    
    print(f"Total Missing Variants: {len(missing_list)}")
    print(f"Total Updated Variants: {len(updated_list)}")
    print(f"Total Images Needed: {len(final_list)}")
    
    # Save as Markdown Artifact
    md_path = 'C:/Users/DELL/.gemini/antigravity/brain/b7f2ef89-1581-40f1-a7cd-48870bb9dcdc/final_extraction_list.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# Final Extraction List (To achieve 100% Accuracy)\n\n")
        f.write(f"Ye total **{len(final_list)} variant codes** ki list hai. In sabhi ki images June PDF se nikalni padengi taaki catalog 100% perfect ho jaye.\n\n")
        f.write(f"- **Missing Images:** {len(missing_list)} variants (jinki photo folder me nahi hai)\n")
        f.write(f"- **Updated Images:** {len(updated_list)} variants (jinki photo June me badal gayi hai)\n\n")
        f.write("## The List:\n")
        for c in final_list:
            f.write(f"- {c.upper()}\n")

if __name__ == '__main__':
    main()
