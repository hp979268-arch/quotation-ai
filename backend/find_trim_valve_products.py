"""
Precisely identify Kohler Trim+Valve products by finding rows in PDF where
a product has BOTH "Trim" label image AND "Valve" label image side by side.

The Kohler PDF layout for trim+valve products is:
[Image of Trim] [Image of Valve]
Trim                Valve
K-XXXXX-CP       K-XXXXX-4
"""

import fitz
import re
import json

PDF_PATH = r"backend/uploads/Kohler_PriceBook (June'26).pdf"
doc = fitz.open(PDF_PATH)

all_trim_valve_pairs = []

for page_num in range(len(doc)):
    page = doc[page_num]
    
    # Get text with position info
    blocks = page.get_text("dict")["blocks"]
    
    # Collect all text spans with their Y positions
    text_lines = []
    for block in blocks:
        if block.get('type') != 0:
            continue
        for line in block.get('lines', []):
            line_text = ' '.join([s['text'] for s in line.get('spans', [])]).strip()
            if line_text:
                y = line['bbox'][1]
                x = line['bbox'][0]
                text_lines.append({'text': line_text, 'y': y, 'x': x, 'bbox': line['bbox']})
    
    # Sort by Y position
    text_lines.sort(key=lambda l: l['y'])
    
    # Find lines that contain "Trim" and "Valve" labels
    # Look for pattern where within ~15px Y range, we have both "Trim" and "Valve" text
    for i, line in enumerate(text_lines):
        if re.search(r'\bTrim\b', line['text'], re.IGNORECASE) and re.search(r'\bValve\b', line['text'], re.IGNORECASE):
            # Both on same line - this is a header like "Trim  Valve"
            # Find product codes near this line (within 200px above or below)
            nearby_codes = []
            for other in text_lines:
                if abs(other['y'] - line['y']) < 200:
                    codes = re.findall(r'K-\d+[A-Z]*(?:IN)?(?:-[\dA-Z]+)*', other['text'])
                    nearby_codes.extend(codes)
            
            if nearby_codes:
                nearby_codes = list(set(nearby_codes))
                all_trim_valve_pairs.append({
                    'page': page_num + 1,
                    'label_line': line['text'][:80],
                    'label_y': line['y'],
                    'nearby_codes': nearby_codes
                })

doc.close()

print(f"Total Trim+Valve combination sections found: {len(all_trim_valve_pairs)}")
print()

# Collect all unique product base codes
all_codes = []
for pair in all_trim_valve_pairs:
    print(f"Page {pair['page']}: '{pair['label_line'][:50]}' (y={pair['label_y']:.0f})")
    print(f"  Codes: {pair['nearby_codes'][:6]}")
    all_codes.extend(pair['nearby_codes'])

unique_base_codes = list(set(all_codes))
unique_base_codes.sort()

print(f"\n{'='*60}")
print(f"TOTAL UNIQUE TRIM+VALVE PRODUCT CODES: {len(unique_base_codes)}")
for c in unique_base_codes:
    print(f"  {c}")

# Save to JSON
with open('backend/trim_valve_products.json', 'w') as f:
    json.dump({
        'total': len(unique_base_codes),
        'codes': unique_base_codes,
        'pages': all_trim_valve_pairs
    }, f, indent=2)

print(f"\nSaved to backend/trim_valve_products.json")
