import os
import re
import csv
from collections import defaultdict


BASE_DIR = os.path.dirname(__file__)
IMAGE_DIR = os.path.join(BASE_DIR, "static", "images", "Kohler")
REPORT_PATH = os.path.join(BASE_DIR, "kohler_image_cleanup_report.csv")


def _code_key(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = stem.strip()
    if not stem.upper().startswith("K-"):
        return ""
    # Remove trailing legacy parenthetical copies like "K-10385IN-AF(K-10385IN-AF)"
    stem = re.sub(r"\s*\(K-[^)]+\)\s*$", "", stem, flags=re.IGNORECASE)
    stem = stem.replace(" ", "")
    return stem.upper()


def _priority(name: str) -> tuple:
    lower = name.lower()
    ext = os.path.splitext(lower)[1]
    # Prefer exact .png, then .jpg/.jpeg, then anything else
    ext_score = 0 if ext == ".png" else 1 if ext in {".jpg", ".jpeg"} else 2
    # Prefer clean names over legacy parenthetical copies / spaced names
    legacy_penalty = 1 if "(" in name or ")" in name or "  " in name or " ." in name else 0
    # Prefer shorter cleaner filenames
    return (ext_score, legacy_penalty, len(name))


def main():
    os.makedirs(IMAGE_DIR, exist_ok=True)
    files = [
        f for f in os.listdir(IMAGE_DIR)
        if os.path.isfile(os.path.join(IMAGE_DIR, f)) and f.lower().startswith("k-")
    ]

    groups = defaultdict(list)
    for f in files:
        key = _code_key(f)
        if key:
            groups[key].append(f)

    kept = {}
    removed = []

    for key, group in groups.items():
        group_sorted = sorted(group, key=_priority)
        keep = group_sorted[0]
        kept[key] = keep
        for f in group_sorted[1:]:
            removed.append(f)

    # Write report first
    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["code", "kept_file", "removed_files"])
        for key in sorted(groups.keys()):
            group = sorted(groups[key], key=_priority)
            writer.writerow([key, group[0], " | ".join(group[1:])])

    # Delete removed files
    for f in removed:
        path = os.path.join(IMAGE_DIR, f)
        try:
            os.remove(path)
        except OSError as e:
            print(f"Failed to remove {f}: {e}")

    print(f"Cleanup report written: {REPORT_PATH}")
    print(f"Codes processed: {len(groups)}")
    print(f"Files kept: {len(kept)}")
    print(f"Files removed: {len(removed)}")


if __name__ == "__main__":
    main()
