import os
import sys
import json
import time
import re
import pymongo

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BACKEND_DIR, "search_index_v2.json")
MONGO_URI = "mongodb+srv://hp979268_db_user:PQo6mPT7DugIoi4f@cluster0.wkcfszp.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

def parse_price_line(line: str):
    """
    Parses formats like:
    - K-20077IN-AF-8500-8550
    - K-20077IN-AF - 8500 - 8550
    - K-20077IN-AF: 8500 -> 8550
    - 2637 AB-49500-51000
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Try pattern with dashes from the right
    # Usually code might have dashes (e.g. K-20077IN-AF)
    # The last two numeric segments are old_price and new_price
    m = re.match(r"^(.*?)[-:\s]+([0-9.,]+)[-\s>]+([0-9.,]+)$", line)
    if m:
        code = m.group(1).strip().rstrip("-").strip()
        old_p = m.group(2).strip().replace(",", "")
        new_p = m.group(3).strip().replace(",", "")
        return {"code": code, "old_price": old_p, "new_price": new_p}

    # Fallback splitting by '-'
    parts = [p.strip() for p in line.split("-") if p.strip()]
    if len(parts) >= 3:
        new_p = parts[-1].replace(",", "")
        old_p = parts[-2].replace(",", "")
        code = "-".join(parts[:-2]).strip()
        return {"code": code, "old_price": old_p, "new_price": new_p}

    return None

def apply_batch(entries, push_mongo=True):
    print(f"Loading {INDEX_PATH}...")
    with open(INDEX_PATH, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    items = data.get("stored_items", [])
    results = []

    for entry in entries:
        code = entry["code"]
        old_price = str(entry.get("old_price", "")).strip()
        new_price = str(entry.get("new_price", "")).strip()

        code_lower = code.lower()
        matched = []

        for idx, item in enumerate(items):
            s_code = str(item.get("search_code") or "").strip().lower()
            b_code = str(item.get("base_code") or "").strip().lower()
            name = str(item.get("name") or "").strip().lower()

            if s_code == code_lower or name.startswith(code_lower):
                matched.append((idx, item))
            elif code_lower in s_code:
                matched.append((idx, item))

        if not matched:
            results.append({"code": code, "status": "NOT_FOUND"})
            print(f"[-] NOT FOUND: {code}")
            continue

        for idx, item in matched:
            curr_p = str(item.get("price") or "").strip()
            item["price"] = new_price
            if "mrp" in item:
                item["mrp"] = new_price

            if item.get("text"):
                if old_price and old_price in item["text"]:
                    item["text"] = item["text"].replace(old_price, new_price)
                elif curr_p and curr_p in item["text"]:
                    item["text"] = item["text"].replace(curr_p, new_price)

            print(f"[+] UPDATED: {item.get('name')} | {curr_p} -> {new_price}")
            results.append({
                "code": code,
                "name": item.get("name"),
                "old_price": curr_p,
                "new_price": new_price,
                "status": "UPDATED"
            })

    updated_count = len([r for r in results if r["status"] == "UPDATED"])
    if updated_count > 0:
        if "version" in data:
            data["version"] = str(int(time.time()))

        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nWrote {updated_count} updates to {INDEX_PATH}")

        # Sync to all packaging and desktop unpacked paths
        import shutil
        sync_targets = [
            os.path.join(BACKEND_DIR, "..", "Quotation_AI_Software_Final", "win-unpacked", "resources", "backend_sidecar", "_internal", "search_index_v2.json"),
            os.path.join(BACKEND_DIR, "..", "frontend", "backend_sidecar_internal", "_internal", "search_index_v2.json"),
            os.path.join(BACKEND_DIR, "..", "frontend", "dist_client", "win-unpacked", "resources", "backend_sidecar", "_internal", "search_index_v2.json"),
            os.path.join(BACKEND_DIR, "dist", "backend_sidecar", "_internal", "search_index_v2.json"),
            os.path.join(BACKEND_DIR, "..", "dist", "backend_sidecar", "_internal", "search_index_v2.json"),
            os.path.join(BACKEND_DIR, "..", "win-unpacked", "resources", "backend_sidecar", "_internal", "search_index_v2.json"),
            os.path.join(BACKEND_DIR, "..", "..", "win-unpacked", "resources", "backend_sidecar", "_internal", "search_index_v2.json"),
        ]
        for t in sync_targets:
            norm_t = os.path.normpath(t)
            if os.path.exists(os.path.dirname(norm_t)):
                try:
                    shutil.copy2(INDEX_PATH, norm_t)
                    print(f"  - Synced to: {norm_t}")
                except Exception as e:
                    print(f"  - Failed copying to {norm_t}: {e}")

        if push_mongo:
            print("Pushing to MongoDB Cloud...")
            client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
            db = client["quotation_ai"]
            doc = dict(data)
            doc["_id"] = "global"
            db["search_index_v3"].replace_one({"_id": "global"}, doc, upsert=True)
            print("SUCCESS: Live MongoDB 'search_index_v3' updated!")

            # Trigger live server reload
            try:
                import urllib.request
                print("Triggering /refresh on live Render backend...")
                req = urllib.request.Request("https://quotation-ai-backend-dn5t.onrender.com/refresh")
                with urllib.request.urlopen(req, timeout=15) as res:
                    print(f"Live server reload response: {res.read().decode()}")
            except Exception as e:
                print(f"Warning: Failed to trigger /refresh on live server: {e}")

    return results

def add_kohler_product(code: str, description: str, price: str, image_path: str = None, brand: str = "Kohler"):
    import shutil, requests, urllib.request
    clean_code = code.strip()
    clean_price = str(price).strip().replace(",", "")

    # Base code: strip finish suffix if present (e.g. K-12345IN-CP -> K-12345IN)
    parts = clean_code.split("-")
    if len(parts) >= 3:
        base_code = "-".join(parts[:-1])
    else:
        base_code = clean_code

    image_urls = []
    if image_path and os.path.exists(image_path):
        # 1. Save to local Kohler image dir
        dest_filename = f"{clean_code}.png"
        local_dest = os.path.join(BACKEND_DIR, "static", "images", brand, dest_filename)
        os.makedirs(os.path.dirname(local_dest), exist_ok=True)
        shutil.copy2(image_path, local_dest)
        print(f"Saved local image: {local_dest}")

        # 2. Copy to all packaging and desktop unpacked paths
        img_targets = [
            os.path.join(BACKEND_DIR, "..", "Quotation_AI_Software_Final", "win-unpacked", "resources", "backend_sidecar", "_internal", "static", "images", brand, dest_filename),
            os.path.join(BACKEND_DIR, "..", "frontend", "backend_sidecar_internal", "_internal", "static", "images", brand, dest_filename),
            os.path.join(BACKEND_DIR, "..", "frontend", "dist_client", "win-unpacked", "resources", "backend_sidecar", "_internal", "static", "images", brand, dest_filename),
            os.path.join(BACKEND_DIR, "dist", "backend_sidecar", "_internal", "static", "images", brand, dest_filename),
            os.path.join(BACKEND_DIR, "..", "dist", "backend_sidecar", "_internal", "static", "images", brand, dest_filename),
            os.path.join(BACKEND_DIR, "..", "win-unpacked", "resources", "backend_sidecar", "_internal", "static", "images", brand, dest_filename),
            os.path.join(BACKEND_DIR, "..", "..", "win-unpacked", "resources", "backend_sidecar", "_internal", "static", "images", brand, dest_filename),
        ]
        for t in img_targets:
            norm_t = os.path.normpath(t)
            if os.path.exists(os.path.dirname(norm_t)):
                shutil.copy2(image_path, norm_t)
                print(f"  - Synced image to: {norm_t}")

        # 3. Upload to live backend
        try:
            with open(image_path, "rb") as f:
                r = requests.post("https://quotation-ai-backend-dn5t.onrender.com/upload-image", files={"file": (dest_filename, f, "image/png")}, timeout=20)
                if r.status_code == 200:
                    live_url = r.json().get("url")
                    print(f"Uploaded to live backend: {live_url}")
                    image_urls.append(live_url)
                    
                    # Mirror uploaded file to local desktop uploads folder too
                    for base_d in [
                        os.path.join(BACKEND_DIR, "static", "images"),
                        os.path.join(BACKEND_DIR, "..", "Quotation_AI_Software_Final", "win-unpacked", "resources", "backend_sidecar", "_internal", "static", "images"),
                        os.path.join(BACKEND_DIR, "..", "frontend", "backend_sidecar_internal", "_internal", "static", "images"),
                        os.path.join(BACKEND_DIR, "..", "frontend", "dist_client", "win-unpacked", "resources", "backend_sidecar", "_internal", "static", "images")
                    ]:
                        sub_path = live_url.replace("/static/images/", "").lstrip("/")
                        full_sub = os.path.normpath(os.path.join(base_d, sub_path))
                        if os.path.exists(os.path.dirname(os.path.dirname(full_sub))):
                            os.makedirs(os.path.dirname(full_sub), exist_ok=True)
                            shutil.copy2(image_path, full_sub)
        except Exception as e:
            print(f"Warning: upload to live server failed: {e}")

        # Fallback local URL
        image_urls.append(f"/static/images/{brand}/{dest_filename}")

    # Build new product item
    new_item = {
        "text": f"{clean_code} - {description}\nMRP : ₹ {clean_price}/-",
        "name": f"{clean_code} - {description}",
        "price": clean_price,
        "mrp": clean_price,
        "images": image_urls if image_urls else [f"/static/images/{brand}/{clean_code}.png"],
        "brand": brand,
        "category": "Faucets & Fittings",
        "search_code": clean_code,
        "base_code": base_code,
        "source": "Manual Addition (Kohler)"
    }

    # Load index
    with open(INDEX_PATH, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    items = data.get("stored_items", [])
    # Check if exists
    found_idx = None
    for idx, it in enumerate(items):
        if str(it.get("search_code") or "").lower() == clean_code.lower():
            found_idx = idx
            break

    if found_idx is not None:
        print(f"Product {clean_code} already exists. Updating existing item...")
        items[found_idx].update(new_item)
    else:
        print(f"Adding brand new product {clean_code}...")
        items.append(new_item)

    data["version"] = str(int(time.time()))
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Sync index to all packaging targets
    sync_targets = [
        os.path.join(BACKEND_DIR, "..", "Quotation_AI_Software_Final", "win-unpacked", "resources", "backend_sidecar", "_internal", "search_index_v2.json"),
        os.path.join(BACKEND_DIR, "..", "frontend", "backend_sidecar_internal", "_internal", "search_index_v2.json"),
        os.path.join(BACKEND_DIR, "..", "frontend", "dist_client", "win-unpacked", "resources", "backend_sidecar", "_internal", "search_index_v2.json"),
        os.path.join(BACKEND_DIR, "dist", "backend_sidecar", "_internal", "search_index_v2.json"),
        os.path.join(BACKEND_DIR, "..", "dist", "backend_sidecar", "_internal", "search_index_v2.json"),
        os.path.join(BACKEND_DIR, "..", "win-unpacked", "resources", "backend_sidecar", "_internal", "search_index_v2.json"),
        os.path.join(BACKEND_DIR, "..", "..", "win-unpacked", "resources", "backend_sidecar", "_internal", "search_index_v2.json"),
    ]
    for t in sync_targets:
        norm_t = os.path.normpath(t)
        if os.path.exists(os.path.dirname(norm_t)):
            shutil.copy2(INDEX_PATH, norm_t)
            print(f"  - Synced index to: {norm_t}")

    # Push to MongoDB
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    db = client["quotation_ai"]
    doc = dict(data)
    doc["_id"] = "global"
    db["search_index_v3"].replace_one({"_id": "global"}, doc, upsert=True)
    print("SUCCESS: Pushed to MongoDB 'search_index_v3'!")

    # Reload live server
    try:
        req = urllib.request.Request("https://quotation-ai-backend-dn5t.onrender.com/refresh")
        with urllib.request.urlopen(req, timeout=15) as res:
            print(f"Live server reload: {res.read().decode()}")
    except Exception as e:
        print(f"Warning: Failed to trigger /refresh on live server: {e}")

    return new_item

if __name__ == "__main__":
    if len(sys.argv) > 1:
        raw_text = " ".join(sys.argv[1:])
        lines = raw_text.splitlines() if "\n" in raw_text else [raw_text]
        entries = []
        for l in lines:
            parsed = parse_price_line(l)
            if parsed:
                entries.append(parsed)
        if entries:
            apply_batch(entries, push_mongo=True)
        else:
            print("No valid price update format recognized.")
