import fitz, re
from PIL import Image
import os

doc = fitz.open(r"backend/uploads/Kohler_PriceBook (June'26).pdf")

# Search all pages for K-29199IN
found_page = None
for pn in range(len(doc)):
    page = doc[pn]
    text = page.get_text()
    if '29199' in text:
        print(f'Found K-29199 on page {pn+1}')
        found_page = pn + 1
        # Extract it
        text_dict = page.get_text("dict")
        for block in text_dict["blocks"]:
            if block.get('type') != 0:
                continue
            bt = ' '.join(s['text'] for l in block.get('lines',[]) for s in l.get('spans',[]))
            if '29199' in bt:
                print(f'  Block: "{bt[:80]}" at {block["bbox"]}')
                
                # Render and crop above this block
                mat = fitz.Matrix(3, 3)
                pix = page.get_pixmap(matrix=mat)
                full = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                
                x0, y0, x1, y1 = block['bbox']
                zoom = 3
                crop = full.crop((
                    max(0, int(x0*zoom)-20),
                    max(0, int(y0*zoom) - int(200*zoom)),
                    min(full.width, int(x1*zoom)+20),
                    int(y0*zoom) - 5
                ))
                
                out = r'backend/static/images/Kohler/K-29199IN-4ND-RGD.png'
                bg = Image.new('RGB', crop.size, (255,255,255))
                bg.paste(crop)
                bg.save(out)
                print(f'  Saved: {crop.size}')

if not found_page:
    print('K-29199 not found in any page!')
    # Try checking K-21969IN-4ND-BV also
    for pn in range(len(doc)):
        page = doc[pn]
        text = page.get_text()
        if '21969' in text:
            print(f'Found K-21969 on page {pn+1}')

doc.close()
