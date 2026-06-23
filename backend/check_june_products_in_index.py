import json
import re

june_only_codes = [
    "K-20702-0", "K-21128IN-2-HB1", "K-21748IN-0", "K-21748IN-2-0",
    "K-22543IN-N-AF", "K-22543IN-N-CP", "K-22544IN-N-AF", "K-22544IN-N-CP",
    "K-23486IN-4ND-BRD", "K-23486IN-4ND-BV", "K-23486IN-4ND-RGD", "K-25759IN-4ND-RGD",
    "K-26343T-NA", "K-26349T-9-CP", "K-26349T-9-RGD", "K-26349W-9-BV",
    "K-26994IN-2-0", "K-26994IN-2-HB1", "K-26995IN-2-0", "K-27478IN-4ND-AF",
    "K-27479IN-4ND-AF", "K-27480IN-4ND-AF", "K-27482IN-4ND-AF", "K-27483IN-4ND-AF",
    "K-27485IN-4-AF", "K-27486IN-4-AF", "K-27488IN-4ND-AF", "K-27490IN-AF",
    "K-27492IN-AF", "K-27493IN-AF", "K-27494IN-AF", "K-27499IN-4FS-AF",
    "K-27500IN-4FS-AF", "K-28513IN-ND-CP", "K-28514IN-ND-CP", "K-28820IN-0",
    "K-29959IN-AF", "K-30318IN-AF", "K-30318IN-BL", "K-30318IN-BV",
    "K-30318IN-CP", "K-30318IN-RGD", "K-30319IN-NA", "K-30457IN-MWF",
    "K-30457IN-PSH", "K-30459IN-MWF", "K-30459IN-N21", "K-30717IN-HNN-UM1",
    "K-30718IN-2HDN-UM1", "K-32014IN-2HDN-UM1", "K-32015IN-HNN-UM1", "K-32018IN-HNN-UM1",
    "K-32387IN-0", "K-33639IN-P-CP", "K-33677IN-0", "K-33678IN-0",
    "K-34098IN-BRD", "K-34099IN-BRD", "K-38362IN-LH0-AF", "K-38362IN-LH0-BL",
    "K-38362IN-LH0-RGD", "K-38362IN-RH0-AF", "K-38362IN-RH0-BL", "K-38362IN-RH0-RGD",
    "K-41652IN-0", "K-5679IN-NA", "K-5683IN-4ND-BRD", "K-5683IN-4ND-BV",
    "K-5683IN-4ND-RGD", "K-5684IN-4ND-BRD", "K-5684IN-4ND-BV", "K-5684IN-4ND-RGD",
    "K-702650IN-LH0-AF", "K-702650IN-LH0-BL", "K-702650IN-LH0-RGD", "K-702650IN-RH0-AF",
    "K-702650IN-RH0-BL", "K-702650IN-RH0-RGD", "K-73039IN-CL-AF", "K-73039IN-CL-BL",
    "K-73040IN-CL-AF", "K-73040IN-CL-BL", "K-99035T-AF", "K-99035T-ZZ-RGD"
]

def check_index():
    with open("search_index_v2.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    missing = []
    no_image = []
    no_price = []
    
    # create a lookup
    index_codes = {}
    for item in data.get("kohler", []):
        name = item.get("name", "")
        # Extract code from name
        match = re.match(r'^((?:[A-Z]{1,3}-\d[A-Z0-9\+\-\ ]*|\d[A-Z0-9\+\-\ ]*))', name, re.IGNORECASE)
        code = match.group(1).strip().upper() if match else name.upper()
        # try simple split
        simple_code = name.split('-')[0] + '-' + name.split('-')[1] if '-' in name else name
        index_codes[name.upper()] = item
        index_codes[name.split()[0].upper()] = item # code usually first word
        
    for code in june_only_codes:
        found = False
        for key, item in index_codes.items():
            if code in key:
                found = True
                
                # Check images
                if not item.get("images"):
                    no_image.append(code)
                
                # Check price
                text = item.get("text", "")
                if "MRP" not in text.upper() and not re.search(r'\d{3,}', text):
                     # might have no price
                     no_price.append(code)
                break
        
        if not found:
            missing.append(code)
            
    print(f"Total checked: {len(june_only_codes)}")
    print(f"Missing completely from index: {len(missing)}")
    if missing:
        print("Missing examples:", missing[:10])
        
    print(f"Present but NO IMAGE: {len(no_image)}")
    if no_image:
        print("No image examples:", no_image[:10])
        
    print(f"Present but possibly NO PRICE: {len(no_price)}")
    if no_price:
        print("No price examples:", no_price[:10])

if __name__ == "__main__":
    check_index()
