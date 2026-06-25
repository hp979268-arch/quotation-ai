import os, base64

files = [
    '30006-30007 BG.png',
    '30006-30007 BRG.png',
    '30006-30007 CP.png',
    '30006-30007 G.png',
    '30006-30007 GG.png',
    '30006-30007 MB.png',
    '30006-30007 RG.png'
]

md = "# 30006-30007 Images\n\n"
for f in files:
    path = os.path.join('c:/Movies/quotation-ai/quotation-ai/backend/static/images/Aquant', f)
    with open(path, 'rb') as img:
        b64 = base64.b64encode(img.read()).decode('utf-8')
    md += f"## {f}\n"
    md += f"<img src='data:image/png;base64,{b64}' width='300'/>\n\n"

with open('C:/Users/DELL/.gemini/antigravity/brain/b7f2ef89-1581-40f1-a7cd-48870bb9dcdc/all_30006_images.md', 'w') as out:
    out.write(md)
print("Done")
