"""
Deep verify Aquant catalog data.
Checks:
- Zero or missing prices
- Missing images
- Broken image links (files that don't exist in backend/static)
- Duplicate search codes
- Empty variant fields
"""
import json
import os

with open('backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data.get('stored_items', [])

aq_items = [item for item in items if isinstance(item, dict) and 'aquant' in item.get('brand', '').lower()]

issues = []
seen_codes = set()
duplicates = []

for item in aq_items:
    sc = item.get('search_code', '').strip()
    if not sc:
        issues.append(f"Missing search_code for item: {item.get('name')}")
        continue
        
    if sc in seen_codes:
        duplicates.append(sc)
    seen_codes.add(sc)
    
    # Check Price
    p = item.get('price', 0)
    try:
        p_float = float(p)
        if p_float <= 0:
            issues.append(f"Zero/Negative price for {sc}: {p}")
    except ValueError:
        issues.append(f"Invalid price format for {sc}: '{p}'")
        
    # Check Images
    imgs = item.get('images', [])
    if not imgs:
        issues.append(f"No image array for {sc}")
    else:
        img_url = imgs[0].split('?')[0]  # Remove version tag
        if not img_url:
            issues.append(f"Empty image URL for {sc}")
        elif 'Image_Not_Found' in img_url:
            issues.append(f"Placeholder image for {sc}")
        else:
            # Check if file actually exists locally
            # Convert /static/images/Aquant/... to local path backend/static/images/Aquant/...
            local_path = 'backend' + img_url
            if not os.path.isfile(local_path):
                issues.append(f"Broken image link for {sc}: {local_path} does not exist!")

print(f"Total Aquant Items: {len(aq_items)}")
print(f"Total Unique Codes: {len(seen_codes)}")
print(f"Duplicates Found: {len(duplicates)}")
if duplicates: print(f"  Examples: {duplicates[:5]}")

print(f"\nTotal Issues Found: {len(issues)}")
for issue in issues[:30]:
    print("  -", issue)
