import csv
import json
import os
import re


BASE_DIR = os.path.dirname(__file__)
INDEX_PATH = os.path.join(BASE_DIR, "search_index_v2.json")
REPORT_PATH = os.path.join(BASE_DIR, "kohler_k_code_image_audit.csv")


def _normalize_code(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip()).upper()


def _extract_code(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return ""
    head = raw.split(" - ", 1)[0].strip()
    return _normalize_code(head)


def _image_stem(image_path: str) -> str:
    filename = os.path.basename(str(image_path or "").strip())
    stem = os.path.splitext(filename)[0]
    return _normalize_code(stem)


def main():
    if not os.path.exists(INDEX_PATH):
        raise FileNotFoundError(f"Missing index file: {INDEX_PATH}")

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("stored_items", []) if isinstance(data, dict) else data

    rows = []
    total_k = 0
    exact_match = 0
    mismatch = 0
    missing = 0

    for item in items:
        if str(item.get("brand", "")).strip().lower() != "kohler":
            continue

        name = str(item.get("name", "")).strip()
        if not name.upper().startswith("K-"):
            continue

        total_k += 1
        code = _extract_code(name)
        images = item.get("images") or []
        matched_images = [img for img in images if _image_stem(img).startswith(code)]

        if not images:
            status = "missing"
            note = "Image Not Found"
            missing += 1
        elif matched_images:
            status = "exact_match"
            note = "Image filename stem matches the product code"
            exact_match += 1
        else:
            status = "mismatch"
            note = "Image Attached, but code mismatch"
            mismatch += 1

        rows.append(
            {
                "brand": "Kohler",
                "product_name": name,
                "code": code,
                "image_count": len(images),
                "first_image": images[0] if images else "",
                "status": status,
                "note": note,
            }
        )

    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "brand",
                "product_name",
                "code",
                "image_count",
                "first_image",
                "status",
                "note",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Report written: {REPORT_PATH}")
    print(f"Total K- items: {total_k}")
    print(f"Exact matches: {exact_match}")
    print(f"Mismatches: {mismatch}")
    print(f"Missing: {missing}")


if __name__ == "__main__":
    main()
