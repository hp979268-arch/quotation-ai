import os

codes = [
    'K-20740IN-A-NA', 'K-26343T-NA', 'K-882IN-NA', 'EX28093IN-8-AF', 'K-25758IN-4ND-AF',
    'K-25757IN-4ND-RGD', 'K-23472IN-4ND-BRD', 'K-72312IN-4ND-BRD', 'K-23486IN-4ND-BRD',
    'K-5683IN-4ND-BRD', 'K-27488IN-4ND-AF', 'K-27490IN-AF', 'K-27493IN-AF', 'K-27499IN-4FS-AF',
    'K-29959IN-AF', 'K-30319IN-NA', 'K-34098IN-BRD', 'K-34099IN-BRD', 'K-73040IN-CL-BL', 'K-99035T-ZZ-RGD'
]

html = '<html><body style="font-family: Arial; padding: 20px;"><h2>Extracted 20 Images from June Catalog</h2><div style="display: flex; flex-wrap: wrap; gap: 20px;">'
for code in codes:
    img_path = f'./static/images/Kohler/{code}.png'
    html += f'''
    <div style="border: 1px solid #ccc; padding: 10px; width: 250px; text-align: center;">
        <img src="{img_path}?v=26" style="max-width: 100%; max-height: 200px;" />
        <p style="font-size: 12px; margin-top: 10px; word-break: break-all;">{code}</p>
    </div>
    '''

html += '</div></body></html>'

with open('backend/extracted_20_gallery.html', 'w', encoding='utf-8') as f:
    f.write(html)
