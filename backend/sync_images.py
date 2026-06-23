import os
import shutil

src = r"c:\Movies\quotation-ai\quotation-ai\backend\static\images\Kohler"
dest = os.path.expandvars(r"%LOCALAPPDATA%\Shreeji Ceramica\static\images\Kohler")

print(f"Syncing {src} -> {dest}")

if os.path.exists(dest):
    # Only copy newer files to save time
    for file in os.listdir(src):
        if not file.endswith('.png') and not file.endswith('.jpg'): continue
        s_path = os.path.join(src, file)
        d_path = os.path.join(dest, file)
        
        # If dest file exists, check if src is newer or size is different
        should_copy = True
        if os.path.exists(d_path):
            s_stat = os.stat(s_path)
            d_stat = os.stat(d_path)
            if s_stat.st_size == d_stat.st_size and s_stat.st_mtime <= d_stat.st_mtime:
                should_copy = False
                
        if should_copy:
            shutil.copy2(s_path, d_path)
            print(f"Copied {file}")
            
    print("Done copying Kohler images.")
else:
    print(f"Destination {dest} does not exist. The app might not be installed here.")
    
# Sync Aquant too just in case
src_aq = r"c:\Movies\quotation-ai\quotation-ai\backend\static\images\Aquant"
dest_aq = os.path.expandvars(r"%LOCALAPPDATA%\Shreeji Ceramica\static\images\Aquant")

if os.path.exists(dest_aq):
    for file in os.listdir(src_aq):
        if not file.endswith('.png') and not file.endswith('.jpg'): continue
        s_path = os.path.join(src_aq, file)
        d_path = os.path.join(dest_aq, file)
        
        should_copy = True
        if os.path.exists(d_path):
            s_stat = os.stat(s_path)
            d_stat = os.stat(d_path)
            if s_stat.st_size == d_stat.st_size and s_stat.st_mtime <= d_stat.st_mtime:
                should_copy = False
                
        if should_copy:
            shutil.copy2(s_path, d_path)
            print(f"Copied {file}")
    print("Done copying Aquant images.")
