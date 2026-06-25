"""
Audit Kohler Images to see why they might be "bigde hue" (messed up/distorted).
"""
import os
import glob
from PIL import Image

IMAGE_DIR = 'backend/static/images/Kohler'
images = glob.glob(os.path.join(IMAGE_DIR, '*.png'))

print(f"Total Kohler Images: {len(images)}")

small_images = 0
large_aspect_ratio = 0
weird_mode = 0
transparent = 0

issues = []

for img_path in images:
    try:
        with Image.open(img_path) as img:
            w, h = img.size
            mode = img.mode
            
            # Check size
            if w < 100 or h < 100:
                small_images += 1
                if len(issues) < 20: issues.append((os.path.basename(img_path), f"Very Small: {w}x{h}"))
                
            # Check aspect ratio
            if h == 0 or w == 0: continue
            ar = w / h
            if ar > 3 or ar < 0.33:
                large_aspect_ratio += 1
                if len(issues) < 20: issues.append((os.path.basename(img_path), f"Extreme Aspect Ratio: {ar:.2f} ({w}x{h})"))
                
            # Check mode
            if mode not in ['RGB', 'RGBA']:
                weird_mode += 1
                if len(issues) < 20: issues.append((os.path.basename(img_path), f"Weird Mode: {mode}"))
                
            if mode == 'RGBA':
                transparent += 1
                
    except Exception as e:
        pass

print("\nSummary of potential issues:")
print(f"Very Small (<100px): {small_images}")
print(f"Extreme Aspect Ratio (distorted?): {large_aspect_ratio}")
print(f"Weird Color Mode: {weird_mode}")
print(f"Transparent background: {transparent}")

print("\nSample of problematic files:")
for item in issues[:20]:
    print(f"{item[0]}: {item[1]}")
