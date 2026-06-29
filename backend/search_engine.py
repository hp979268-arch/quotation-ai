from dotenv import load_dotenv
load_dotenv()
import bisect
import copy
import json
import os
import re
import threading
import unicodedata
import sys
from datetime import datetime

# Priority environment setup
is_frozen = getattr(sys, 'frozen', False)
EXE_DIR = os.path.dirname(os.path.abspath(sys.executable)) if is_frozen else os.path.dirname(os.path.abspath(__file__))
_MEIPASS = getattr(sys, '_MEIPASS', EXE_DIR)
BUNDLED_DIR = _MEIPASS
if is_frozen:
    possible_internal = os.path.join(_MEIPASS, "_internal")
    if os.path.isdir(possible_internal):
        BUNDLED_DIR = possible_internal

# Heavy AI libraries are temporarily disabled to prevent Windows environment hangs
# from sentence_transformers import SentenceTransformer
# import torch

import numpy as np
import cloud_storage
import mongodb
from app_paths import resolve_data_dir

DATA_DIR = resolve_data_dir(is_frozen, EXE_DIR)

# Priority path for search index
INDEX_FILE_PERSISTENT = os.path.join(DATA_DIR, "search_index_v2.json")
INDEX_FILE_BUNDLED = os.path.join(BUNDLED_DIR, "search_index_v2.json")
INDEX_FILE = INDEX_FILE_PERSISTENT

# Persistent cache for image paths to speed up startup
IMAGE_CACHE_FILE = os.path.join(DATA_DIR, "image_path_cache.json")
IMAGE_CACHE_FILE_BUNDLED = os.path.join(BUNDLED_DIR, "image_path_cache.json")

# AI Search is disabled to ensure stability on all Windows systems
AI_AVAILABLE = False
model = None
_model_lock = threading.Lock()
_model_loading = False

def _load_model_background():
    global model, AI_AVAILABLE, _model_loading
    AI_AVAILABLE = False
    _model_loading = False
    print("Semantic Model Disabled (Stable Keyword-only mode active).")

def ensure_model_loaded():
    """Trigger model loading if not already started."""
    pass

# REMOVED: immediate load on import
# ensure_model_loaded()

# Try loading FAISS
FAISS_AVAILABLE = False
faiss = None
try:
    import faiss as _faiss
    faiss = _faiss
    FAISS_AVAILABLE = True
    print("FAISS Loaded OK.")
except Exception as e:
    print(f"Warning: FAISS not available: {e}")


# ---- Global State ----
stored_items = []
keyword_index = {}   # word -> [item_indices]
_keyword_keys_sorted = []  # sorted list of keyword_index keys for O(log n) prefix lookup
vector_index  = None # FAISS index
search_cache  = {}   # query -> results
catalog_summary_cache = None # Saved dashboard index
item_code_meta_cache = {}
_index_cache_signature = None
_image_path_cache = None
_resolved_code_to_image_cache = {}
_suggestion_cache = {}   # (query_lower, brand_lower) -> suggestion list
_SUGGESTION_CACHE_MAX = 200  # max entries to avoid unbounded memory
CACHE_SCHEMA_VERSION = 2
HARD_PLACEHOLDER_CODES = {
    "K-24740IN-7", "K-24740IN-K4", "K-17663IN-0", "K-82958",
    "K-1042534", "K-1060831", "K-1063956", "K-1286731",
}
HARD_PLACEHOLDER_IMAGE = "/static/images/Kohler/Image_Not_Found.png"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, str(default))).strip().lower()
    return raw in {"1", "true", "yes", "on"}


REMOTE_INDEX_SYNC_ENABLED = _env_flag("SEARCH_INDEX_REMOTE_SYNC", is_frozen)


# INDEX_FILE is now dynamically determined in load_index
SEARCH_INDEX_OBJECT_PATH = os.getenv("SUPABASE_SEARCH_INDEX_PATH", "search/search_index_v2.json")

STATIC_IMAGES_DIR = os.path.join(BUNDLED_DIR, "static", "images")
PERSISTENT_IMAGES_DIR = os.path.join(DATA_DIR, "static", "images")
IMAGE_ROOTS = []
for _root in (PERSISTENT_IMAGES_DIR, STATIC_IMAGES_DIR, os.path.join(BUNDLED_DIR, "static", "images")):
    if _root and _root not in IMAGE_ROOTS:
        IMAGE_ROOTS.append(_root)

# Minimum file size (bytes) for a valid product image.
# Images below this are icons, colour swatches, or small decorative elements from the PDF.
_MIN_PRODUCT_IMAGE_SIZE = 1000
SUPPORTED_BRANDS = {"aquant", "kohler"}

_LEADING_CODE_WITH_VARIANT_RE = re.compile(
    r'^\s*((?:[A-Z]{1,4}-\d[A-Z0-9\+\-\ ]*|\d[A-Z0-9\+\-\ ]*))(?:\s+([A-Z0-9+]{1,12}))?',
    re.IGNORECASE,
)
_KNOWN_FINISH_LABELS = {
    "AB": "Antique Bronze",
    "AC": "Antique Chrome",
    "AN": "Antique Nickel",
    "B": "Glossy Black",
    "BC": "Beige Caramel",
    "BCG": "Black Champagne Gold",
    "BG": "Brushed Gold",
    "BCK": "Matt Black",
    "BRG": "Brushed Rose Gold",
    "BSS": "Brushed Stainless Steel Finish",
    "CB": "Chrome Black",
    "CGY": "Chrome Grey",
    "CH": "Chrome",
    "CM": "Carrara Marble",
    "CNG": "Champagne Gold",
    "CP": "Chrome Plated",
    "CW": "Chrome White",
    "G": "Gold",
    "GB": "Glossy Black",
    "GG": "Graphite Grey/Glossy Gold",
    "GM": "Gun Metal",
    "GRY": "Matt Grey",
    "LG": "Lunar Grey",
    "MB": "Matt Black",
    "MG": "Matt Grey",
    "MI": "Matt Ivory",
    "LM": "Lavender Marble (Chevron Amethyst)",
    "MW": "Matt White/White",
    "OG": "Olive Green",
    "ORB": "Oil Rubbed Bronze",
    "RB": "Royal Blue",
    "RG": "Rose Gold",
    "BM": "Marquina Marble",
    "PP": "Pink Paradise (Pink Onyx)",
    "RGB": "Rose Gold/Matt Black",
    "RGD": "Rose Gold",
    "RGW": "Rose Gold/Matt White",
    "RN": "Royal Navy",
    "SB": "Sky Blue",
    "SG": "Seafoam Green",
    "SN": "Satin Nickel",
    "SSF": "Brushed Stainless Steel",
    "TCR": "Terracotta Red",
    "W": "White",
    "WCG": "White Champagne Gold",
    "WG": "White Glass",
    "WN": "Walnut",
    "WRG": "White Rose Gold",
    "WTE": "Matt White",
    # Kohler Finishes
    "0": "White",
    "7": "Black Black",
    "AF": "Vibrant French Gold",
    "BN": "Vibrant Brushed Nickel",
    "BV": "Vibrant Brushed Bronze",
    "BGD": "Vibrant Moderne Brushed Gold",
    "2MB": "Vibrant Brushed Moderne Brass",
    "TT": "Vibrant Titanium",
    "VS": "Vibrant Stainless",
    "BL": "Matte Black",
    "GP1": "Gold",
    "GP2": "Brushed Gold",
}
_KNOWN_FINISH_CODES = tuple(sorted(_KNOWN_FINISH_LABELS.keys(), key=len, reverse=True))


def _image_file_size(image_path: str) -> int:
    """Return the file size of a /static/images/... path, or -1 if missing."""
    full = _resolve_local_image_path(image_path)
    if not full:
        return -1
    try:
        return os.path.getsize(full)
    except OSError:
        return -1


def _resolve_local_image_path(image_path: str) -> str:
    if not image_path:
        return ""

    rel = str(image_path).lstrip("/")
    rel = rel.replace("static/images/", "", 1)
    rel = rel.replace("static/", "", 1)

    for root in IMAGE_ROOTS:
        full = os.path.abspath(os.path.normpath(os.path.join(root, rel)))
        if not full.startswith(os.path.abspath(root)):
            continue
        if os.path.exists(full):
            return full

    return ""


def _is_page_extracted_image(image_path: str) -> bool:
    """True when the image path clearly points to a PDF-extracted segment instead of a dedicated product photo."""
    if not image_path:
        return False
    basename = os.path.basename(image_path)
    return bool(re.search(r'_p\d+_i\d+|Page', basename, re.IGNORECASE))


def _is_cover_page_image(image_path: str) -> bool:
    """True when the image clearly comes from a PDF cover / title page."""
    if not image_path:
        return False
    basename = os.path.basename(image_path)
    # Matches patterns like  Brand_..._p0_i3.jpg  and  Brand_..._p1_i0.jpg
    import re as _re
    return bool(_re.search(r'_p[012]_i', basename))


def _normalize_variant_token(token: str) -> str:
    token = re.sub(r'\s+', '', str(token or "").upper())
    token = token.strip("-_/+")
    if not token:
        return ""
    return "+".join(part for part in token.split("+") if part)


def _is_likely_finish_token(token: str) -> bool:
    normalized = _normalize_variant_token(token)
    if not normalized:
        return False

    parts = [part for part in normalized.split("+") if part]
    if not parts:
        return False

    return all(part in _KNOWN_FINISH_LABELS for part in parts)


def _split_attached_finish_token(code: str):
    normalized = str(code or "").strip().upper()
    if not normalized:
        return "", ""

    # Plain numeric model codes like "4000" or "4010" should stay intact.
    # Treating the trailing 0/7 as a finish token breaks exact code search.
    if normalized.isdigit():
        return normalized, ""

    combo_match = re.match(
        r'^((?:[A-Z]{1,4}-\d[A-Z0-9-]*|\d[\d-]*))([A-Z]{1,4}(?:\+[A-Z]{1,4})+)$',
        normalized,
    )
    if combo_match:
        base_code = combo_match.group(1).strip()
        variant_code = _normalize_variant_token(combo_match.group(2))
        if base_code and _is_likely_finish_token(variant_code):
            return base_code, variant_code

    if "-" in normalized:
        maybe_base, maybe_variant = normalized.rsplit("-", 1)
        maybe_variant = _normalize_variant_token(maybe_variant)
        if maybe_base and _is_likely_finish_token(maybe_variant) and re.search(r'\d', maybe_base):
            return maybe_base.strip(), maybe_variant

    for finish_code in _KNOWN_FINISH_CODES:
        if not normalized.endswith(finish_code):
            continue
        maybe_base = normalized[:-len(finish_code)].strip()
        if maybe_base and re.search(r'\d', maybe_base):
            return maybe_base, finish_code

    return normalized, ""


def _format_finish_label(variant_code: str) -> str:
    normalized = _normalize_variant_token(variant_code)
    if not normalized:
        return ""
    return " + ".join(_KNOWN_FINISH_LABELS.get(part, part) for part in normalized.split("+") if part)

def _clean_display_text(text: str) -> str:
    """Normalize common mojibake/bullet artifacts for UI display."""
    if not text:
        return ""
    
    # Try fixing common double-encoding issues first
    s = unicodedata.normalize("NFKC", _try_fix_mojibake(str(text)))
    
    # Comprehensive replacement map for common encoding artifacts
    replacements = {
        "â€¢": "-", "â€“": "-", "â€”": "-", "â€™": "'", "â€œ": '"', "â€?": '"',
        "Ã¢-žÂ¢": "™", "Ã¢â‚¬â„¢": "'", "Ã¢â‚¬": "-", "â–": "-", "â–=": "-",
        "â\x9e¢": "™", "â\x84¢": "™", "\u2022": "-", "\u2122": " TM ",
        "\u20b9": "Rs ", "â‚¹": "Rs ", "Ã‚": "", "Â": " ",
        "\u00a0": " ", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "â€“": "-", "â€”": "-",
    }
    for bad, good in replacements.items():
        s = s.replace(bad, good)
        
    # Catch any remaining common double-encoded artifacts like Ã¢ or Ã
    s = re.sub(r'Ã[¢\-\sžÂ]+[¢Â]?', '™', s)
    s = s.replace("Ã", "")
    s = s.replace("â", "")
        
    # Normalize bullet-like glyphs to a simple dash for cleaner UI.
    for bullet in ("•", "●", "▪", "◦", "◾", "■", "•"):
        s = s.replace(bullet, "-")
        
    # Collapse extra spaces
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def _strip_mrp_lines(text: str) -> str:
    """Remove lines starting with 'MRP' to avoid redundant price display in UI/PDF."""
    if not text:
        return ""
    lines = str(text).splitlines()
    filtered = [line for line in lines if not re.search(r'^\s*MRP\b', line, re.IGNORECASE)]
    return "\n".join(filtered).strip()


def _try_fix_mojibake(value: str) -> str:
    text = str(value or "")
    if not any(ch in text for ch in ("Ã", "â", "Â")):
        return text
    try:
        repaired = text.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
        if repaired:
            return repaired
    except Exception:
        pass
    return text


def _is_supported_brand_name(brand_name: str) -> bool:
    return str(brand_name or "").strip().lower() in SUPPORTED_BRANDS


def _is_supported_item(item) -> bool:
    return _is_supported_brand_name(_item_brand(item))


def _image_brand_hint(image_path: str) -> str:
    rel_path = str(image_path or "").replace("\\", "/").strip().lstrip("/")
    if rel_path.lower().startswith("static/images/"):
        rel_path = rel_path[len("static/images/"):]
    first_segment = rel_path.split("/", 1)[0].strip().lower()
    return first_segment if first_segment in SUPPORTED_BRANDS else ""


def _clean_variant_prices(variant_prices):
    if not isinstance(variant_prices, dict):
        return variant_prices
    cleaned = {}
    for key, value in variant_prices.items():
        cleaned[_clean_display_text(key)] = value
    return cleaned


def prepare_item_for_display(item):
    display_item = copy.deepcopy(item)
    raw_name = _clean_display_text(display_item.get("name"))
    raw_text = _clean_display_text(display_item.get("text"))
    display_name = raw_name
    display_code = display_item.get("search_code") or display_item.get("full_code") or display_item.get("base_code") or ""
    if raw_name and _looks_like_model_code(raw_name) and raw_text:
        text_head = raw_text.splitlines()[0].strip()
        if text_head and not _looks_like_model_code(text_head):
            display_name = text_head
    elif not raw_name and raw_text:
        display_name = raw_text.splitlines()[0].strip()

    for key in (
        "name",
        "text",
        "category",
        "brand",
        "source",
        "sku",
        "size",
        "search_code",
        "base_code",
        "full_code",
        "finish_label",
    ):
        if key in display_item:
            display_item[key] = _clean_display_text(display_item.get(key))

    if "variant_prices" in display_item:
        display_item["variant_prices"] = _clean_variant_prices(display_item.get("variant_prices"))

    # Check if this product is a hard-placeholder (no real image ever assigned)
    _code_meta_disp = _get_item_code_metadata(item)
    _is_placeholder_code = any(
        c in HARD_PLACEHOLDER_CODES
        for c in (
            _code_meta_disp.get("full_code", ""),
            _code_meta_disp.get("base_code", ""),
            str(item.get("search_code", "")),
        )
        if c
    )
    if _is_placeholder_code:
        display_item["images"] = []
    else:
        best_image = _best_item_image(item)
        if best_image:
            display_item["images"] = [best_image]
        else:
            # Only keep image paths that actually exist on disk and are not page-extracted
            verified = [
                img for img in (display_item.get("images") or [])
                if img and _resolve_local_image_path(img) and not _is_page_extracted_image(img)
            ]
            display_item["images"] = verified

    # Normalize a few Aquant ceiling-shower variants whose OCR'd finish labels
    # can include an extra color that should not be shown in the UI.
    code_blob = f"{raw_name} {raw_text} {display_code}".lower()
    if any(token in code_blob for token in ("5104 gg", "5105 gg", "5106 gg", "5107 gg")):
        display_item["finish_label"] = "Graphite Grey"
    elif any(token in code_blob for token in ("5104 bg", "5105 bg", "5106 bg", "5107 bg")):
        display_item["finish_label"] = "Brushed Gold"

    display_item["display_name"] = _clean_display_text(display_name)
    display_item["display_code"] = _clean_display_text(display_code)
    if raw_text:
        display_item["display_text"] = _strip_mrp_lines(raw_text)

    return display_item


def prepare_items_for_display(items):
    return [prepare_item_for_display(item) for item in items if item]

def _parse_code_metadata(raw_text: str):
    text = str(raw_text or "").strip()
    if not text:
        return {
            "base_code": "",
            "variant_code": "",
            "full_code": "",
            "base_compact": "",
            "variant_compact": "",
            "full_compact": "",
            "finish_label": "",
        }

    header = text.splitlines()[0].strip()
    header = re.split(r'\s+-\s+', header, maxsplit=1)[0].strip()
    header = re.sub(r'\bMRP\b.*$', '', header, flags=re.IGNORECASE).strip(" -:")
    if not header:
        return {
            "base_code": "",
            "variant_code": "",
            "full_code": "",
            "base_compact": "",
            "variant_compact": "",
            "full_compact": "",
            "finish_label": "",
        }

    match = _LEADING_CODE_WITH_VARIANT_RE.match(header)
    if match:
        base_code = (match.group(1) or "").strip().upper()
        variant_code = _normalize_variant_token(match.group(2))
        if variant_code and not _is_likely_finish_token(variant_code):
            variant_code = ""
        if not variant_code:
            base_code, variant_code = _split_attached_finish_token(base_code)
    else:
        base_code, variant_code = _split_attached_finish_token(header.upper())

    full_code = base_code
    if variant_code:
        full_code = f"{base_code} {variant_code}".strip()

    return {
        "base_code": base_code,
        "variant_code": variant_code,
        "full_code": full_code,
        "base_compact": _compact_alnum(base_code),
        "variant_compact": _compact_alnum(variant_code),
        "full_compact": _compact_alnum(full_code),
        "finish_label": _format_finish_label(variant_code),
    }


def _get_item_code_metadata(item):
    cache_key = id(item)
    cached = item_code_meta_cache.get(cache_key)
    if isinstance(cached, dict) and cached.get("full_code") is not None:
        return cached

    # Prefer any code metadata already present on the item. This matters for
    # catalogs where the stored index has been normalized offline (for example
    # Aquant families like 1330 CI/IR/MT/GS/AO) and avoids re-parsing raw text
    # back into an older, less accurate split.
    stored_base = str(item.get("base_code", "")).strip().upper()
    stored_variant = _normalize_variant_token(item.get("variant_code", ""))
    stored_search = str(item.get("search_code", "")).strip().upper()
    if stored_base:
        full_code = stored_search or stored_base
        if not full_code.startswith(stored_base):
            full_code = stored_base
            if stored_variant:
                full_code = f"{stored_base} {stored_variant}".strip()
        elif not stored_variant and full_code != stored_base:
            stored_variant = _normalize_variant_token(full_code[len(stored_base):].strip())

        meta = {
            "base_code": stored_base,
            "variant_code": stored_variant,
            "full_code": full_code,
            "base_compact": _compact_alnum(stored_base),
            "variant_compact": _compact_alnum(stored_variant),
            "full_compact": _compact_alnum(full_code),
            "finish_label": item.get("finish_label") or _format_finish_label(stored_variant),
        }
        item_code_meta_cache[cache_key] = meta
        return meta

    for raw in (
        item.get("code", ""),
        item.get("name", ""),
        str(item.get("text", "")).split("\n")[0],
    ):
        meta = _parse_code_metadata(raw)
        if meta["base_code"]:
            item["base_code"] = meta["base_code"]
            item["variant_code"] = meta["variant_code"]
            item["search_code"] = meta["full_code"]
            if meta["finish_label"] and not item.get("finish_label"):
                item["finish_label"] = meta["finish_label"]
            item_code_meta_cache[cache_key] = meta
            return meta

    empty = _parse_code_metadata("")
    item_code_meta_cache[cache_key] = empty
    return empty


def _enrich_items_for_search(items):
    needed = False
    for item in items:
        # Optimization: only enrich if key fields are missing
        if "base_compact" not in item:
            _get_item_code_metadata(item)
            needed = True
    return needed


def _item_quality_bonus(item) -> float:
    bonus = 0.0
    price = str(item.get("price") or "").strip()
    name = str(item.get("name") or "").strip()

    if price and price != "0":
        bonus += 60.0
    else:
        bonus -= 80.0

    if item.get("images"):
        bonus += 18.0

    if " - " in name:
        bonus += 10.0
    if "+ -" in name or name.endswith(" +"):
        bonus -= 45.0
    if len(name) >= 24:
        bonus += 6.0

    return bonus


def _sanitize_item_images(items):
    """
    Skipped since images are now correctly pre-processed and extracted by model number.
    """
    pass


def _normalize_item_images(items):
    global _resolved_code_to_image_cache
    _resolved_code_to_image_cache.clear()
    
    # Run 3 passes to allow image resolution to propagate to variant/sibling codes
    for pass_num in range(3):
        for item in items or []:
            best_image = _best_item_image(item)
            if best_image:
                item["images"] = [best_image]

def save_index():
    global stored_items, keyword_index
    # _sanitize_item_images(stored_items)
    # _normalize_item_images(stored_items)
    data = {
        "stored_items": stored_items,
        "keyword_index": keyword_index
    }
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"Index saved to {INDEX_FILE}")

    # Synchronously save image cache too
    if _image_path_cache:
        try:
            payload = {"__schema__": CACHE_SCHEMA_VERSION, "paths": _image_path_cache}
            with open(IMAGE_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            if IMAGE_CACHE_FILE_BUNDLED and IMAGE_CACHE_FILE_BUNDLED != IMAGE_CACHE_FILE:
                with open(IMAGE_CACHE_FILE_BUNDLED, "w", encoding="utf-8") as f:
                    json.dump(payload, f)
        except Exception as e:
            print(f"Warning: failed to save image cache: {e}")

    if cloud_storage.is_enabled():
        try:
            cloud_storage.upload_file(
                cloud_storage.SYSTEM_BUCKET,
                SEARCH_INDEX_OBJECT_PATH,
                INDEX_FILE,
                "application/json",
            )
            print("Index synced to cloud storage.")
        except Exception as e:
            print(f"Warning: failed to sync index to cloud storage: {e}")

def load_index(force: bool = False):
    global stored_items, keyword_index, vector_index, search_cache, catalog_summary_cache, item_code_meta_cache, _index_cache_signature
    
    # print(f"DEBUG: load_index(force={force})")
    
    # 1. Decide which index file to use and perform automatic sync
    index_file = INDEX_FILE_PERSISTENT
    
    # NEW: Automatic Sync Logic
    # If we are in a bundled environment, check if the bundled index should overwrite the persistent one.
    if os.path.exists(INDEX_FILE_BUNDLED):
        needs_sync = False
        if not os.path.exists(INDEX_FILE_PERSISTENT):
            needs_sync = True
        else:
            # Sync if bundled file is newer OR significantly different in size
            bundled_mtime = os.path.getmtime(INDEX_FILE_BUNDLED)
            persistent_mtime = os.path.getmtime(INDEX_FILE_PERSISTENT)
            if bundled_mtime > (persistent_mtime + 5): # 5 second buffer
                needs_sync = True
        
        if needs_sync:
            try:
                import shutil
                with open("backend_debug.txt", "a") as f:
                    f.write(f"{datetime.now()} - Syncing index files...\n")
                shutil.copy2(INDEX_FILE_BUNDLED, INDEX_FILE_PERSISTENT)
                with open("backend_debug.txt", "a") as f:
                    f.write(f"{datetime.now()} - Syncing done.\n")
                print(f"Automatic Sync: Overwrote persistent index with latest bundled version.")
                # Also clear the image cache to be safe
                if os.path.exists(IMAGE_CACHE_FILE):
                    os.remove(IMAGE_CACHE_FILE)
            except Exception as e:
                with open("backend_debug.txt", "a") as f:
                    f.write(f"{datetime.now()} - Sync Error: {e}\n")
                print(f"Sync Warning: Failed to auto-sync index: {e}")

    if not os.path.exists(index_file):
        index_file = INDEX_FILE_BUNDLED
        
    if not os.path.exists(index_file) and cloud_storage.is_enabled():
        try:
            restored = cloud_storage.download_to_path(
                cloud_storage.SYSTEM_BUCKET,
                SEARCH_INDEX_OBJECT_PATH,
                index_file,
            )
            if restored:
                print("Restored search index from cloud storage.")
        except Exception as e:
            print(f"Warning: failed to restore index from cloud storage: {e}")

    # Check if MongoDB is enabled and has the search index in cloud
    loaded_from_mongo = False
    if mongodb.is_enabled():
        try:
            mongo_data = mongodb.load_search_index()
            if mongo_data:
                stored_items = mongo_data.get("stored_items", [])
                keyword_index = mongo_data.get("keyword_index", {})
                print(f"Index loaded dynamically: {len(stored_items)} items loaded from MongoDB Cloud!")
                _index_cache_signature = "mongodb"
                loaded_from_mongo = True
        except Exception as e:
            print(f"Warning: Failed to load search index from MongoDB: {e}")

    if not loaded_from_mongo and os.path.exists(index_file):
        try:
            signature = (index_file, os.path.getmtime(index_file), os.path.getsize(index_file))
            if not force and stored_items and _index_cache_signature == signature:
                return True

            with open(index_file, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                stored_items = data.get("stored_items", [])
                keyword_index = data.get("keyword_index", {})
            print(f"Index loaded: {len(stored_items)} items from {index_file}")
            _index_cache_signature = signature

            # Auto-seed MongoDB if enabled but empty
            if mongodb.is_enabled():
                try:
                    mongodb.save_search_index(data)
                except Exception as e:
                    print(f"Warning: Failed to seed MongoDB: {e}")

        except Exception as e:
            print(f"Error loading local index: {e}")

    if stored_items:
        try:
            item_code_meta_cache = {}
            _enrich_items_for_search(stored_items)
            search_cache.clear()

            # Strip bad/wrong product images (cover logos, tiny icons, missing files)
            # _sanitize_item_images(stored_items)
            # _normalize_item_images(stored_items)

            # Reset caches
            search_cache = {}
            catalog_summary_cache = None
            _suggestion_cache.clear()

            # Build sorted keyword key list for fast bisect prefix lookup
            _keyword_keys_sorted[:] = sorted(keyword_index.keys())

            # Rebuild FAISS in background to avoid blocking API
            if AI_AVAILABLE and FAISS_AVAILABLE and stored_items:
                threading.Thread(target=_rebuild_faiss_background, daemon=True).start()

            return True
        except Exception as e:
            print(f"Error initializing index data: {e}")
            return False
            
    return False

def _rebuild_faiss_background():
    global vector_index
    print("Background FAISS rebuild started...")
    try:
        texts = [item["text"] for item in stored_items]
        batch_size = 256
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_embeddings = model.encode(batch_texts, convert_to_numpy=True, show_progress_bar=False)
            all_embeddings.append(batch_embeddings)
        
        embeddings = np.vstack(all_embeddings).astype(np.float32)
        faiss.normalize_L2(embeddings)
        dim = embeddings.shape[1]
        v_idx = faiss.IndexFlatIP(dim)
        v_idx.add(embeddings)
        vector_index = v_idx
        print("Background FAISS rebuild complete.")
    except Exception as e:
        print(f"FAISS rebuild failed: {e}")

def reset_index():
    global stored_items, keyword_index, vector_index, search_cache, catalog_summary_cache, item_code_meta_cache, _suggestion_cache
    stored_items   = []
    keyword_index  = {}
    vector_index   = None
    search_cache   = {}
    catalog_summary_cache = None
    item_code_meta_cache = {}
    _suggestion_cache = {}  # Clear suggestion cache on index reset
    _keyword_keys_sorted.clear()
    if os.path.exists(INDEX_FILE):
        try:
            os.remove(INDEX_FILE)
        except OSError as e:
            # The file may be temporarily locked on Windows; save_index() will overwrite it.
            print(f"Warning: could not remove old index file, will overwrite on save: {e}")
    if cloud_storage.is_enabled():
        try:
            cloud_storage.delete_object(cloud_storage.SYSTEM_BUCKET, SEARCH_INDEX_OBJECT_PATH)
        except Exception as e:
            print(f"Warning: failed to delete cloud search index: {e}")


def _normalize(text, strip_in=False):
    # Remove common separators and non-essential chars
    t = re.sub(r'[\s\-\/\.\_\u2013\u2014]+', '', text.lower())
    if strip_in:
        t = t.replace('in', '')
    return t

def _code_like(text: str) -> bool:
    return bool(re.search(r'[a-z]', text.lower())) and bool(re.search(r'\d', text))

def _compact_alnum(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', text.lower())

def _clean_kohler_numeric_code(code: str) -> str:
    c = str(code or "").strip().lower()
    if c.startswith('k') and len(c) > 1 and c[1].isdigit():
        c = c[1:]
    if c.endswith('in') and len(c) > 2 and c[:-2].isdigit():
        c = c[:-2]
    elif c.endswith('t') and len(c) > 1 and c[:-1].isdigit():
        c = c[:-1]
    return c


def _looks_like_model_code(text: str) -> bool:
    """True if the string contains a digit and likely represents a product code."""
    if not text: return False
    return bool(re.search(r'\d', text))

def _build_image_path_cache():
    global _image_path_cache
    if _image_path_cache is not None:
        return _image_path_cache

    # 1. Try loading from persistent file first
    for path in [IMAGE_CACHE_FILE, IMAGE_CACHE_FILE_BUNDLED]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                    if isinstance(payload, dict) and payload.get("__schema__") == CACHE_SCHEMA_VERSION:
                        cached_paths = payload.get("paths", {})
                        if isinstance(cached_paths, dict):
                            _image_path_cache = cached_paths
                            print(f"Loaded image path cache from {path}: {len(_image_path_cache)} entries")
                            return _image_path_cache
                    print(f"Ignoring legacy image cache at {path}; rebuilding for brand-folder support.")
            except Exception as e:
                print(f"Warning: image cache file error at {path}: {e}")

    # 2. Walk directory if cache missing or failed
    cache = {}
    # Check both persistent and bundled image roots.
    for img_root in IMAGE_ROOTS:
        if os.path.isdir(img_root):
            print(f"Walking image directory to build cache: {img_root}")
            for root, _, files in os.walk(img_root):
                for filename in files:
                    stem = os.path.splitext(filename)[0]
                    stems = [stem]
                    if "(" in stem:
                        stems.append(stem.split("(")[0].strip())
                    if "[" in stem:
                        stems.append(stem.split("[")[0].strip())
                    
                    rel_dir = os.path.relpath(root, img_root).replace("\\", "/")
                    rel_path = f"{filename}" if rel_dir == "." else f"{rel_dir}/{filename}"
                    public_path = f"/static/images/{rel_path}"
                    
                    seen_compacts = set()
                    for s_item in stems:
                        compact = _compact_alnum(s_item)
                        if compact and compact not in seen_compacts:
                            seen_compacts.add(compact)
                            cache.setdefault(compact, []).append(public_path)

    _image_path_cache = cache
    # Save newly built cache
    try:
        with open(IMAGE_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"__schema__": CACHE_SCHEMA_VERSION, "paths": cache}, f)
    except Exception:
        pass
        
    return cache


def _pick_best_image_match(item, matches):
    if not matches:
        return None

    item_brand = _item_brand(item)

    def sort_key(path: str):
        normalized = str(path or "").replace("\\", "/").lower()
        brand_hint = _image_brand_hint(path)
        brand_score = 10 if item_brand and brand_hint == item_brand else 1 if brand_hint else 0
        cover_penalty = -5 if _is_cover_page_image(path) else 0
        
        # Prioritize files in the brand's own subfolder (Kohler/ or Aquant/)
        in_brand_folder = 0
        if item_brand:
            brand_folder_part = f"/{item_brand.lower()}/"
            if brand_folder_part in normalized:
                in_brand_folder = 20
                
        folder_boost = 5 if "/" in normalized and not normalized.startswith("manual/") else 0
        manual_penalty = -1 if "/manual/" in normalized else 0
        depth_penalty = -normalized.count("/")
        return (in_brand_folder, brand_score, folder_boost, cover_penalty, manual_penalty, depth_penalty)

    return max(matches, key=sort_key)


def _best_item_image(item):
    """Prefer a verified image path from disk or one of the already assigned ones."""
    global _resolved_code_to_image_cache
    
    code_meta = _get_item_code_metadata(item)
    base_code = code_meta.get("base_code", "")
    full_code = code_meta.get("full_code", "")
    
    # 1. Check resolved cache first for exact variant (full_code)
    if full_code and full_code in _resolved_code_to_image_cache:
        return _resolved_code_to_image_cache[full_code]

    # Collect all candidate files from the item itself
    candidates = []
    for img_path in (item.get("images") or []):
        if img_path and _image_file_size(img_path) >= _MIN_PRODUCT_IMAGE_SIZE:
            if _is_page_extracted_image(img_path):
                continue
            candidates.append(img_path)
            
    candidate_codes = []
    for key in ("full_code", "search_code", "base_code"):
        value = str(item.get(key, "") or code_meta.get(key, "")).strip()
        if value:
            candidate_codes.append(value)
            
    name = item.get("name", "")
    text = item.get("text", "")
    
    parentheses_candidates = []
    for source in [name, text] + candidate_codes:
        if source:
            found = re.findall(r'\(([^)]+)\)', str(source))
            for f in found:
                parentheses_candidates.append(f.strip())

    candidate_codes = [c for c in candidate_codes if c]
    image_cache = _build_image_path_cache()

    # Hard-coded placeholder handling
    for code in candidate_codes:
        if code in HARD_PLACEHOLDER_CODES:
            compact = _compact_alnum(code)
            if compact and compact in image_cache:
                pass
            else:
                return None



    # Add candidates from disk cache via exact match
    for code in candidate_codes:
        compact_code = _compact_alnum(code)
        if not compact_code:
            continue
        matches = image_cache.get(compact_code)
        if matches:
            for m in matches:
                if _is_page_extracted_image(m):
                    continue
                if m not in candidates and _image_file_size(m) >= _MIN_PRODUCT_IMAGE_SIZE:
                    candidates.append(m)

    if candidates:
        res = _pick_best_image_match(item, candidates)
        if res:
            if full_code:
                _resolved_code_to_image_cache[full_code] = res
            return res

    # 2. Extract lookup keys: base_code, full_code, other K-codes found in descriptions
    ordered_keys = []
    if full_code:
        ordered_keys.append(_compact_alnum(full_code))
    if base_code:
        ordered_keys.append(_compact_alnum(base_code))
        
    # Extract any K-XXXXXX codes from name and text that are different from the base code
    all_k_codes = re.findall(r'K-\d{4,}\w*[-#\w]*', name + " " + text)
    for kc in all_k_codes:
        kc_clean = kc.strip()
        kc_meta = _get_item_code_metadata({"search_code": kc_clean, "base_code": kc_clean})
        kc_base = kc_meta.get("base_code", "")
        if kc_base and kc_base.lower() != base_code.lower():
            ordered_keys.append(_compact_alnum(kc_clean))
            ordered_keys.append(_compact_alnum(kc_base))
            
    # Include parentheses candidates
    for pc in parentheses_candidates:
        ordered_keys.append(_compact_alnum(pc))
        
    # Sibling/Variant Pruning
    for key in list(ordered_keys):
        if "-" in key:
            parts = key.split("-")
            if len(parts) > 1:
                ordered_keys.append(_compact_alnum(parts[0]))
                
    # Extract digit strings (4+ digits)
    digit_fallback_keys = []
    for k in ordered_keys:
        m_digits = re.findall(r'\d{4,}', k)
        for d in m_digits:
            digit_fallback_keys.append(d)
            if len(d) > 4:
                digit_fallback_keys.append(d[:4])
                
    # Deduplicate ordered_keys preserving order
    seen = set()
    unique_keys = []
    for k in ordered_keys:
        if k and k not in seen:
            seen.add(k)
            unique_keys.append(k)

    res_img = None

    # Exact & Prefix match on unique_keys
    for k in unique_keys:
        valid_matches = []
        for cache_key, paths in image_cache.items():
            if cache_key.startswith(k) or k in cache_key:
                for p in paths:
                    if _is_page_extracted_image(p):
                        continue
                    if _image_file_size(p) >= _MIN_PRODUCT_IMAGE_SIZE:
                        valid_matches.append(p)
        if valid_matches:
            res_img = _pick_best_image_match(item, valid_matches)
            break

    # Digits Match on 4+ digit prefixes
    if not res_img:
        for d in digit_fallback_keys:
            valid_matches = []
            for cache_key, paths in image_cache.items():
                if d in cache_key:
                    for p in paths:
                        if _is_page_extracted_image(p):
                            continue
                        if _image_file_size(p) >= _MIN_PRODUCT_IMAGE_SIZE:
                            valid_matches.append(p)
            if valid_matches:
                res_img = _pick_best_image_match(item, valid_matches)
                break

    if res_img:
        if full_code:
            _resolved_code_to_image_cache[full_code] = res_img
        return res_img

    if base_code and base_code in _resolved_code_to_image_cache:
        return _resolved_code_to_image_cache[base_code]

    return None

    return None



def _special_family_override_items(query_code_meta, brand_lower: str):
    """
    Some product families intentionally span multiple nearby codes.
    Keep these grouped so search returns the intended set instead of
    leaking in visually similar combo products.
    """
    base_compact = query_code_meta.get("base_compact", "")
    variant_compact = query_code_meta.get("variant_compact", "")
    if base_compact != "1333" or variant_compact:
        return []

    allowed_compacts = {"1333cm", "1333bm", "1333pp", "1333rb", "11333lm"}
    picked = []
    for item in stored_items:
        if not _is_supported_item(item):
            continue
        if brand_lower and brand_lower != "all" and _item_brand(item) != brand_lower:
            continue
        meta = _get_item_code_metadata(item)
        if meta.get("full_compact") in allowed_compacts:
            picked.append(item)

    order = {code: idx for idx, code in enumerate(["1333cm", "1333bm", "11333lm", "1333pp", "1333rb"])}
    picked.sort(key=lambda item: order.get(_get_item_code_metadata(item).get("full_compact", ""), 999))
    return picked

def _code_relaxed(compact_code: str) -> str:
    # Handle common OCR confusion in model codes: O/0 and I/L/1.
    return (
        (compact_code or "")
        .lower()
        .replace("o", "0")
        .replace("i", "1")
        .replace("l", "1")
    )

def _extract_compound_code_tokens(text: str):
    cleaned = re.sub(r'[\r\n\t]+', ' ', str(text or '').lower())
    tokens = re.findall(r'\b(?:[a-z]{1,4}[-/]?\d{2,}|\d{3,})(?:\s+[a-z]{1,3}){1,2}\b', cleaned)
    seen = set()
    ordered = []
    for tok in tokens:
        normalized = re.sub(r'\s+', ' ', tok).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered

def _is_code_or_model_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    tokens = re.findall(r'[a-z0-9/\-\+]+', q)
    if not tokens:
        return False

    if _extract_compound_code_tokens(q):
        return True

    # If any token itself looks like a model/code, treat as strict code query
    for tok in tokens:
        if re.fullmatch(r'[a-z]{1,5}[-/]?\d{2,}[a-z0-9/-]*', tok):
            return True

    # Single-token numeric or mixed token queries are likely direct code searches
    if len(tokens) == 1 and re.fullmatch(r'\d{3,}', tokens[0]):
        return True
    if len(tokens) == 1 and bool(re.search(r'[a-z]', tokens[0])) and bool(re.search(r'\d', tokens[0])) and len(tokens[0]) >= 4:
        return True
    numeric_tokens = [tok for tok in tokens if re.fullmatch(r'\d{3,}', tok)]
    if numeric_tokens:
        known_brands = {"kohler", "aquant", "plumber"}
        if len(tokens) <= 3 and any(tok in known_brands for tok in tokens):
            return True

    return False

def _extract_model_tokens(text: str):
    # Handles model patterns like K-12345IN, 9272, 2594CP, etc.
    seen = set()
    ordered = []

    for tok in _extract_compound_code_tokens(text):
        if tok not in seen:
            seen.add(tok)
            ordered.append(tok)

    for tok in re.findall(r'[a-z]{1,4}[-/]?\d{2,}[a-z0-9/-]*|\b\d{3,}\b', text.lower()):
        if tok not in seen:
            seen.add(tok)
            ordered.append(tok)

    return ordered


def _exact_name_variants(item):
    name = str(item.get("name") or "").strip()
    text = str(item.get("text") or "").strip()
    first_line = text.split("\n")[0].strip() if text else name
    base_line = first_line or name

    variants = []
    for raw in (name, first_line, base_line):
        cleaned = raw.strip()
        if cleaned and cleaned not in variants:
            variants.append(cleaned)

    parts = [part.strip() for part in base_line.split(" - ") if part.strip()]
    
    # NEW: Handle Kohler style "Title (Code)" or "Title Code"
    if not parts or len(parts) < 2:
        # Try finding a bracketed code or a trailing K- code
        m = re.search(r'^(.*?)\s*[\(\[]?\s*(K-\d[A-Z0-9-]*)\s*[\)\]]?$', base_line, re.IGNORECASE)
        if m:
            parts = [m.group(1).strip(), m.group(2).strip()]
            
    if parts:
        head = parts[0]
        tail_parts = parts[1:] if (_extract_model_tokens(head) or bool(re.search(r'\d', head))) else parts
        if tail_parts:
            joined_dash = " - ".join(tail_parts)
            joined_space = " ".join(tail_parts)
            for raw in (joined_dash, joined_space):
                cleaned = raw.strip()
                if cleaned and cleaned not in variants:
                    variants.append(cleaned)

    return variants


def _exact_name_score(item, query: str) -> float:
    query = (query or "").strip()
    if not query:
        return 0.0

    query_lower = query.lower()
    query_compact = _compact_alnum(query)
    query_has_digits = bool(re.search(r'\d', query_lower))
    query_norm = _normalize(query, strip_in=query_has_digits)

    best = 0.0
    variants = _exact_name_variants(item)
    if not variants:
        return 0.0

    for idx, variant in enumerate(variants):
        variant_lower = variant.lower()
        variant_compact = _compact_alnum(variant)
        variant_norm = _normalize(variant, strip_in=query_has_digits)

        if query_compact and variant_compact == query_compact:
            score = 4200.0 - (idx * 10.0)
            best = max(best, score)
            continue

        if query_norm and len(query_norm) >= 3 and variant_norm == query_norm:
            score = 4100.0 - (idx * 10.0)
            best = max(best, score)
            continue

        if variant_lower == query_lower:
            score = 4000.0 - (idx * 10.0)
            best = max(best, score)

    return best

def _item_brand(item):
    brand = (item.get("brand") or "").strip()
    if brand:
        return brand.lower()
    source = str(item.get("source") or "").lower()
    if "kohler" in source:
        return "kohler"
    if "aquant" in source:
        return "aquant"
    if "plumber" in source:
        return "plumber"
    return ""

def add_to_index(_unused_embeddings, items):
    global stored_items, keyword_index, vector_index, search_cache

    search_cache = {}
    _enrich_items_for_search(items)
    start_idx = len(stored_items)
    stored_items.extend(items)

    for i, item in enumerate(items):
        idx = start_idx + i
        text = item.get("text", "")
        name = item.get("name", "")
        brand = item.get("brand", "")
        source = item.get("source", "")
        search_blob = f"{brand} {name}\n{text} {source}".strip()
        blob_lower = search_blob.lower()

        # Build list of unique tokens to index
        words_to_index = set()

        # 1. Broad split on any separator (including en-dash, dots, etc)
        tokens = re.split(r'[\s\-\/\.\_\u2013\u2014\(\)\[\],:;]+', blob_lower)
        for w in tokens:
            w = w.strip()
            if len(w) >= 2:
                words_to_index.add(w)
                # If it looks like model/code like K12345IN, store normalized variant as well.
                if _code_like(w):
                    words_to_index.add(_normalize(w, strip_in=True))

        # 2. Extract model/code tokens explicitly (e.g. k-12345in, 9272, 2594cp)
        for model_tok in _extract_model_tokens(search_blob):
            words_to_index.add(model_tok)
            norm_tok = _normalize(model_tok, strip_in=True)
            compact_tok = _compact_alnum(model_tok)
            if len(norm_tok) >= 3:
                words_to_index.add(norm_tok)
            if len(compact_tok) >= 3:
                words_to_index.add(compact_tok)

        code_meta = _get_item_code_metadata(item)
        for meta_key in ("base_code", "variant_code", "full_code"):
            meta_value = code_meta.get(meta_key, "")
            if not meta_value:
                continue
            words_to_index.add(meta_value.lower())
            compact_value = _compact_alnum(meta_value)
            normalized_value = _normalize(meta_value, strip_in=True)
            if len(compact_value) >= 3:
                words_to_index.add(compact_value)
            if len(normalized_value) >= 3:
                words_to_index.add(normalized_value)

        # Also index search_code directly (handles bundle codes like "K-30520IN-0 + K-8705IN-0")
        raw_search_code = str(item.get("search_code", "")).strip()
        if raw_search_code:
            words_to_index.add(raw_search_code.lower())
            # Index all numeric parts so "30520" finds "K-30520IN-0 + K-8705IN-0"
            for num_part in re.findall(r'\d{4,}', raw_search_code):
                words_to_index.add(num_part)

        # 3. Add normalized name and first text slice for combined code-name queries
        norm_name = _normalize(name, strip_in=True)
        norm_head = _normalize(text[:120], strip_in=True)
        if len(norm_name) >= 3:
            words_to_index.add(norm_name)
        if len(norm_head) >= 3:
            words_to_index.add(norm_head)

        for w in words_to_index:
            if w:
                keyword_index.setdefault(w, []).append(idx)

    # FAISS Vector Indexing
    if AI_AVAILABLE and FAISS_AVAILABLE:
        try:
            texts      = [item["text"] for item in items]
            embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            embeddings = embeddings.astype(np.float32)
            faiss.normalize_L2(embeddings)

            if vector_index is None:
                dim = embeddings.shape[1]
                vector_index = faiss.IndexFlatIP(dim)

            vector_index.add(embeddings)
            print(f"Indexed {len(items)} blocks (total: {len(stored_items)})")
        except Exception as e:
            print(f"Embedding error: {e}")

    save_index()
    # Rebuild sorted key list for fast bisect prefix search in get_suggestions
    _keyword_keys_sorted[:] = sorted(keyword_index.keys())
    _suggestion_cache.clear()



def search(query: str, smart: bool = False, brand: str = None):
    global stored_items, keyword_index
    
    query = query.strip()
    if not query:
        return []
    
    # Only reload when the index is empty (cold start).
    # This avoids an expensive MongoDB round-trip on every keystroke.
    if not stored_items:
        load_index()
    if not stored_items:
        return []

    brand_lower = (brand or "").strip().lower()
    if brand_lower and brand_lower != "all" and not _is_supported_brand_name(brand_lower):
        return []
    is_all_brand = (not brand_lower) or (brand_lower == "all")
    cache_key = f"{query}|{smart}|{brand_lower}"
    if cache_key in search_cache:
        return search_cache[cache_key]

    query_lower = query.lower()
    query_words = [w for w in re.split(r'[\s\-\/\.\_\u2013\u2014]+', query_lower) if len(w) >= 2]
    query_alnum = re.sub(r'[^a-z0-9]+', '', query_lower)
    query_has_digits = bool(re.search(r'\d', query_lower))
    is_code_query = _is_code_or_model_query(query)
    query_norm = _normalize(query, strip_in=query_has_digits)
    query_model_tokens = _extract_model_tokens(query)
    query_model_norms = {_normalize(tok, strip_in=True) for tok in query_model_tokens if len(tok) >= 2}
    query_compact = _compact_alnum(query)
    query_code_meta = _parse_code_metadata(query)
    query_base_compact = query_code_meta.get("base_compact", "")
    query_variant_compact = query_code_meta.get("variant_compact", "")
    query_full_compact = query_code_meta.get("full_compact", "")

    special_family = _special_family_override_items(query_code_meta, brand_lower)
    if special_family:
        search_cache[cache_key] = special_family
        return special_family

    # Prefer an explicit code-like token from the query (e.g. "kohler K-28220T-SL-0").
    strict_query_compact = ""
    if query_full_compact:
        strict_query_compact = query_full_compact
    for tok in query_model_tokens:
        if strict_query_compact:
            break
        tok_compact = _compact_alnum(tok)
        if len(tok_compact) >= 3 and bool(re.search(r'[a-z]', tok_compact)) and bool(re.search(r'\d', tok_compact)):
            strict_query_compact = tok_compact
            break
    if not strict_query_compact:
        for tok in query_model_tokens:
            tok_compact = _compact_alnum(tok)
            if len(tok_compact) >= 3 and tok_compact.isdigit():
                strict_query_compact = tok_compact
                break
    if not strict_query_compact:
        strict_query_compact = query_compact

    # 1. RETRIEVE CANDIDATES FAST
    candidate_indices = set()
    lookup_keys = set(query_words)
    if len(query_alnum) >= 3:
        lookup_keys.add(query_alnum)
    if len(query_norm) >= 3:
        lookup_keys.add(query_norm)
    for model_tok in query_model_tokens:
        if len(model_tok) >= 2:
            lookup_keys.add(model_tok)
    for model_norm in query_model_norms:
        if len(model_norm) >= 3:
            lookup_keys.add(model_norm)
    for meta_value in (
        query_code_meta.get("base_code", ""),
        query_code_meta.get("variant_code", ""),
        query_code_meta.get("full_code", ""),
        query_base_compact,
        query_variant_compact,
        query_full_compact,
    ):
        if len(str(meta_value or "").strip()) >= 1:
            lookup_keys.add(str(meta_value).lower())

    # Expand lookup keys for Kohler numeric codes
    extra_lookup_keys = set()
    for key in lookup_keys:
        if key.isdigit() and len(key) >= 3:
            extra_lookup_keys.add(f"k{key}")
            extra_lookup_keys.add(f"k{key}in")
            extra_lookup_keys.add(f"{key}in")
    lookup_keys.update(extra_lookup_keys)

    for key in lookup_keys:
        if key in keyword_index:
            candidate_indices.update(keyword_index[key])
        
    # If no direct hits, do a partial lookup fallback.
    if not candidate_indices and (len(query_alnum) >= 3 or len(query_lower) >= 4):
        for kindex in keyword_index:
            if (query_alnum and query_alnum in kindex) or (query_lower in kindex):
                candidate_indices.update(keyword_index[kindex])
                if len(candidate_indices) > 300:
                    break

    if not candidate_indices:
        # For model/code queries, do a strict full scan fallback.
        if is_code_query:
            candidate_indices = set(range(len(stored_items)))
        else:
            return []

    # 2. FILTER & SCORE (Limited to candidates)
    indices_list = list(candidate_indices)
    if not is_all_brand:
        # Strictly filter down to the selected brand
        indices_list = [idx for idx in indices_list if _item_brand(stored_items[idx]) == brand_lower]
        if not indices_list:
            return []
    else:
        indices_list = [idx for idx in indices_list if _is_supported_item(stored_items[idx])]
        if not indices_list:
            return []

    # STRICT MODE: code/model queries should resolve to one most-accurate hit.
    if is_code_query:
        query_code = strict_query_compact
        query_is_numeric = query_code.isdigit()
        query_code_relaxed = _code_relaxed(query_code)
        strict_scores = {}
        for idx in indices_list:
            item = stored_items[idx]
            item_code_meta = _get_item_code_metadata(item)
            name_lower = str(item.get("name") or "").lower()
            text_lower = str(item.get("text") or "").lower()
            # Restrict strict matching to header lines before "MRP" to avoid price-number noise.
            header_lines = []
            for raw_line in text_lower.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue
                if "mrp" in line:
                    break
                header_lines.append(line)
                if len(header_lines) >= 6:
                    break
            if not header_lines:
                header_lines = [ln.strip() for ln in text_lower.split("\n")[:3] if ln.strip()]

            blob = f"{name_lower}\n" + "\n".join(header_lines)
            token_compacts = []
            for tok in _extract_model_tokens(blob):
                tok_compact = _compact_alnum(tok)
                if len(tok_compact) >= 3:
                    token_compacts.append(tok_compact)
            best = 0.0
            quality_bonus = _item_quality_bonus(item)

            # If the query points at a specific base code, keep strict matching
            # inside that family so combo products like "1334 BG + 1333" do not
            # leak into a plain "1333" search.
            if query_base_compact and item_code_meta.get("base_compact") not in {query_base_compact, ""}:
                item_base_compact = item_code_meta.get("base_compact", "")
                
                # Check cleaned Kohler numeric codes
                q_clean = _clean_kohler_numeric_code(query_base_compact)
                i_clean = _clean_kohler_numeric_code(item_base_compact)
                
                if q_clean and q_clean == i_clean:
                    pass
                elif item_base_compact.endswith(query_base_compact):
                    pass
                elif not (
                    query_full_compact
                    and item_code_meta.get("full_compact") == query_full_compact
                ):
                    continue

            if query_full_compact and item_code_meta.get("full_compact"):
                item_full_compact = item_code_meta["full_compact"]
                if item_full_compact == query_full_compact:
                    best = max(best, 3700.0 + quality_bonus)
                elif _code_relaxed(item_full_compact) == _code_relaxed(query_full_compact):
                    best = max(best, 3620.0 + quality_bonus)

            # If base compact matches (either exactly or cleaned Kohler-wise)
            q_clean = _clean_kohler_numeric_code(query_base_compact)
            item_bc = item_code_meta.get("base_compact", "")
            i_clean = _clean_kohler_numeric_code(item_bc)
            
            base_matched = query_base_compact and (item_bc == query_base_compact or (q_clean and q_clean == i_clean))

            if base_matched:
                if query_variant_compact:
                    if item_code_meta.get("variant_compact") == query_variant_compact:
                        best = max(best, 3520.0 + quality_bonus)
                    elif item_code_meta.get("variant_compact"):
                        best = max(best, 2380.0 + quality_bonus)
                    else:
                        best = max(best, 2250.0 + quality_bonus)
                else:
                    best = max(best, 3040.0 + quality_bonus)

            # Highest confidence: exact compact token equality (with OCR-tolerant equivalent).
            has_exact_code = any(
                (tok_compact == query_code) or 
                (_code_relaxed(tok_compact) == query_code_relaxed) or 
                (_clean_kohler_numeric_code(tok_compact) == _clean_kohler_numeric_code(query_code))
                for tok_compact in token_compacts
            )
            if has_exact_code:
                line_exact = any(_compact_alnum(line) == query_code for line in header_lines[:4])
                best = max(best, 3000.0 + (80.0 if line_exact else 0.0) + quality_bonus)
            
            # Smart Partial Logic: If query matches start of a token (e.g. "K-277" matches "K-27792IN")
            # give it a mid-range score so it appears above generic fuzzy hits.
            if best < 2500 and len(query_code) >= 4:
                prefix_match = any(tok_compact.startswith(query_code) for tok_compact in token_compacts)
                if prefix_match:
                    best = max(best, 2400.0 + quality_bonus)
            elif best < 2000 and len(query_code) >= 3:
                # Shorter prefix match also gets a boost over totally unrelated items
                prefix_match = any(tok_compact.startswith(query_code) for tok_compact in token_compacts)
                if prefix_match:
                    best = max(best, 1900.0 + quality_bonus)

            if best == 0 and query_is_numeric:
                # Numeric-only search: allow exact numeric segment only (not broad substring).
                seg_match = False
                for tok_compact in token_compacts:
                    segments = re.findall(r'\d{3,}', tok_compact)
                    if query_code in segments:
                        seg_match = True
                        break
                if seg_match:
                    line_has = any(re.search(rf'(^|\D){re.escape(query_code)}(\D|$)', line) for line in header_lines[:4])
                    best = max(best, 1700.0 + (60.0 if line_has else 0.0) + quality_bonus)

            if best > 0:
                strict_scores[idx] = best

        if strict_scores:
            ranked_strict = sorted(strict_scores.items(), key=lambda x: (-x[1], x[0]))

            # Find all products that share a high enough score (allowing for variants with different quality bonuses)
            top_score = ranked_strict[0][1]
            top_candidates = [stored_items[idx] for idx, score in ranked_strict if score >= (top_score - 800)]

            # PERMANENT SOLUTION: We only want ONE accurate, primary product block for a given code.
            # If the parser split things weirdly, we remove duplicate variations of the EXACT same item name.
            unique_candidates = []
            seen_names = set()
            for cand in top_candidates:
                # Use a simplified name to check for duplicates
                cand_name = re.sub(r'[^a-zA-Z0-9]', '', cand.get("name", "").lower())
                if cand_name not in seen_names:
                    seen_names.add(cand_name)
                    unique_candidates.append(cand)

            # INCREASED: Show more variants (e.g. all 12+ finishes for a code)
            max_exact_results = 15
            results = unique_candidates[:max_exact_results]
            
            search_cache[cache_key] = results
            return results
        
        # PERMANENT: If the algorithm proved it's a code search ("7512 OG", "1186 RG") and we didn't
        # hit perfectly exact above, we fall through to fuzzy but we MUST limit it to a reasonable set, 
        # so it doesn't give you random irrelevant stuff but still shows variants.
        fuzzy_max = 12
    else:
        # For non-code queries (like "wash basin", "olive green"), allow more results 
        # so user can see options, but cap to a reasonable number.
        fuzzy_max = 30

    scores = {}
    
    for idx in indices_list:
        item = stored_items[idx]
        item_code_meta = _get_item_code_metadata(item)
        name_lower = str(item.get("name") or "").lower()
        text_lower = str(item.get("text") or "").lower()
        combined = f"{name_lower}\n{text_lower}"
        first_line = text_lower.split('\n')[0] if text_lower else ""
        s = 0.0
        
        # Priority 1: Normalized match (best for model/code)
        if len(query_norm) >= 3:
            combined_norm = _normalize(combined, strip_in=query_has_digits)
            if query_norm in combined_norm:
                s += 550.0

        # Priority 2: Exact model token match
        if query_model_tokens:
            combined_code_norm = _normalize(combined, strip_in=True)
            for tok in query_model_tokens:
                tok_norm = _normalize(tok, strip_in=True)
                if tok in combined:
                    s += 300.0
                elif len(tok_norm) >= 3 and tok_norm in combined_code_norm:
                    s += 280.0

        if query_base_compact and item_code_meta.get("base_compact") == query_base_compact:
            s += 260.0
        if query_full_compact and item_code_meta.get("full_compact") == query_full_compact:
            s += 520.0
        if query_variant_compact:
            item_variant_compact = item_code_meta.get("variant_compact")
            if item_variant_compact == query_variant_compact:
                s += 340.0
            elif item_variant_compact:
                s -= 180.0

        # Priority 3: Name / first-line / text relevance
        if query_lower in name_lower:
            s += 380.0
        if query_lower in first_line:
            s += 300.0
        elif query_lower in text_lower:
            s += 120.0
        
        # Word overlap
        for w in query_words:
            if w in combined:
                s += 45.0
                if w in name_lower or w in first_line:
                    s += 35.0

        # Bonus when every query token is present.
        if query_words and all(w in combined for w in query_words):
            s += 140.0

        s += _item_quality_bonus(item)

        if s > 0:
            scores[idx] = s

    # 3. SEMANTIC BOOST (Optional & Skipped for codes)
    is_mostly_digits = len(re.findall(r'\d', query)) > len(re.findall(r'[a-zA-Z]', query))
    if smart and AI_AVAILABLE and FAISS_AVAILABLE and vector_index is not None and not is_mostly_digits:
        try:
            q_emb = model.encode([query], convert_to_numpy=True, show_progress_bar=False)
            q_emb = q_emb.astype(np.float32)
            faiss.normalize_L2(q_emb)
            k = min(100, vector_index.ntotal)
            D, I = vector_index.search(q_emb, k)
            for dist, s_idx in zip(D[0], I[0]):
                if s_idx >= 0 and dist > 0.4:
                    if (is_all_brand and _is_supported_item(stored_items[s_idx])) or brand_lower == _item_brand(stored_items[s_idx]):
                        scores[s_idx] = scores.get(s_idx, 0) + float(dist) * 150.0
        except Exception: pass

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    # Filter out weak scores (require 400+ for code matches, 350+ for texts)
    min_score = 400 if is_code_query else 350
    
    # Filter and validate items before slicing
    filtered_items = []
    for idx, score in ranked:
        if score < min_score:
            continue
            
        item = stored_items[idx]
        if not _is_supported_item(item):
            continue
        
        # If the user typed a specific code modifier like "OG" or "RG", drop results that clearly don't have it
        if is_code_query and len(query_words) > 1:
            item_text_lower = (item.get("name", "") + " " + item.get("text", "")).lower()
            missing_modifier = False
            for w in query_words:
                if not w.isdigit() and len(w) <= 3:
                    # Look for the color modifier surrounded by non-alphanumeric chars or start/end of string
                    pattern = r'(?:^|[^a-zA-Z0-9])' + re.escape(w) + r'(?:[^a-zA-Z0-9]|$)'
                    if not re.search(pattern, item_text_lower):
                        missing_modifier = True
                        break
            if missing_modifier:
                continue

        filtered_items.append((item, score))

    if is_code_query and query_variant_compact:
        exact_variant_items = []
        for item, score in filtered_items:
            item_code_meta = _get_item_code_metadata(item)
            if (
                item_code_meta.get("variant_compact") == query_variant_compact
                or item_code_meta.get("full_compact") == query_full_compact
            ):
                exact_variant_items.append((item, score))
        if exact_variant_items:
            filtered_items = exact_variant_items
        
    max_results = fuzzy_max

    if is_all_brand and not is_code_query:
        # Keep "all brands" balanced, so both PDFs are visible when both have matches.
        buckets = {}
        for item, score in filtered_items:
            b = _item_brand(item) or "generic"
            buckets.setdefault(b, []).append(item)

        ordered_brands = [b for b in ("aquant", "kohler") if b in buckets]
        ordered_brands.extend([b for b in buckets.keys() if b not in ordered_brands])

        mixed_items = []
        while len(mixed_items) < max_results:
            progressed = False
            for b in ordered_brands:
                if buckets[b]:
                    mixed_items.append(buckets[b].pop(0))
                    progressed = True
                    if len(mixed_items) >= max_results:
                        break
            if not progressed:
                break
        results = mixed_items
    else:
        results = [item for item, score in filtered_items[:max_results]]

    # Deduplicate purely by base name to avoid multiple identical images cluttering
    unique_res = []
    seen = set()
    for item in results:
        base_name = re.sub(r'[^a-zA-Z0-9]', '', item.get("name", "").lower())
        if base_name not in seen:
            seen.add(base_name)
            unique_res.append(item)
            if len(unique_res) >= max_results:
                break

    display_results = prepare_items_for_display(unique_res)
    search_cache[cache_key] = display_results
    return display_results


def search_exact(query: str, smart: bool = False, brand: str = None):
    query = (query or "").strip()
    if not query:
        return []

    load_index()
    if not stored_items:
        return []

    brand_lower = (brand or "").strip().lower()
    if brand_lower and brand_lower != "all" and not _is_supported_brand_name(brand_lower):
        return []
    if brand_lower and brand_lower != "all":
        target_brands = [brand_lower]
    else:
        target_brands = [b for b in ("aquant", "kohler") if any(_item_brand(item) == b for item in stored_items)]
        if not target_brands:
            target_brands = [""]

    query_is_code = _is_code_or_model_query(query)
    results = []

    for target_brand in target_brands:
        best_exact_item = None
        best_exact_score = 0.0

        if not query_is_code:
            for item in stored_items:
                if not _is_supported_item(item):
                    continue
                item_brand = _item_brand(item)
                if target_brand and item_brand != target_brand:
                    continue
                score = _exact_name_score(item, query)
                if score > best_exact_score:
                    best_exact_score = score
                    best_exact_item = item

        if best_exact_item is not None:
            results.append(best_exact_item)
            continue

        fallback = search(query, smart=smart, brand=(target_brand or None))
        if fallback:
            results.append(fallback[0])

    unique_res = []
    seen = set()
    for item in results:
        dedupe_key = f"{_item_brand(item)}|{_compact_alnum(item.get('name', ''))}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        unique_res.append(item)

    return prepare_items_for_display(unique_res)


def _items_to_suggestion_payload(items, limit: int = 50):
    final_results = []
    seen = set()
    for item in items:
        if not _is_supported_item(item):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue

        display_item = prepare_item_for_display(item)
        item_code_meta = _get_item_code_metadata(item)
        parts = name.split(" - ", 1)
        code = _clean_display_text(parts[0].strip() or item_code_meta.get("full_code") or name)
        description = _clean_display_text(parts[1].strip()) if len(parts) > 1 else ""
        if not item_code_meta.get("full_code") and not _extract_model_tokens(code):
            # Catalog entries without a visible model code should still surface
            # by their product name instead of showing an empty code bucket.
            description = description or code
            code = ""
        full_name = _clean_display_text(name)
        dedupe_key = f"{str(item.get('brand') or '').lower()}|{full_name.lower()}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        best_img = _best_item_image(item)
        # Raw item already has images stripped/verified by prepare_item_for_display;
        # mirror that here so the top-level 'image' field is consistent.
        final_results.append({
            "text": code,
            "description": description,
            "full_name": full_name,
            "display_name": display_item.get("display_name") or full_name,
            "display_code": display_item.get("display_code") or code,
            "brand": _clean_display_text(item.get("brand", "Aquant")),
            "image": best_img if best_img else None,
            "price": item.get("price"),
            "raw_item": display_item,
        })
        if len(final_results) >= limit:
            break
    return final_results


def _merge_suggestion_payloads(*payload_groups, limit: int = 50):
    merged = []
    seen = set()
    for group in payload_groups:
        for item in group or []:
            key = f"{str(item.get('brand') or '').lower()}|{str(item.get('full_name') or item.get('text') or '').lower()}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= limit:
                return merged
    return merged


def get_suggestions(query: str, limit: int = 50, brand: str = None):
    global _suggestion_cache
    if not query or len(query.strip()) < 2:
        return []

    # Start model loading in background if it's the first search
    ensure_model_loaded()

    # Only call load_index() when the in-memory index is empty (e.g. cold start).
    # Skipping it on every keystroke eliminates the expensive MongoDB round-trip
    # that was the primary cause of slow suggestions on the live site.
    if not stored_items:
        load_index()
    if not stored_items:
        return []

    q_raw = query.strip()
    brand_lower_ck = (brand or "").strip().lower()
    cache_key = (q_raw.lower(), brand_lower_ck)
    if cache_key in _suggestion_cache:
        return _suggestion_cache[cache_key]

    q = query.strip().lower()
    q_compact = _compact_alnum(q)
    brand_lower = (brand or "").strip().lower()
    if brand_lower and brand_lower != "all" and not _is_supported_brand_name(brand_lower):
        return []
    is_all_brand = (not brand_lower) or (brand_lower == "all")

    exact_name_items = []
    
    global _suggestion_precompute_cache
    if '_suggestion_precompute_cache' not in globals():
        _suggestion_precompute_cache = {}
        
    for item in stored_items:
        if not _is_supported_item(item):
            continue
        if not is_all_brand and _item_brand(item) != brand_lower:
            continue
            
        item_id = id(item)
        if item_id not in _suggestion_precompute_cache:
            item_name = str(item.get("name") or "").strip().lower()
            item_text = str(item.get("text") or "").strip().lower()
            item_code = str(item.get("search_code") or item.get("base_code") or "").strip().lower()
            item_alias = str(item.get("display_name") or "").strip().lower()
            
            _suggestion_precompute_cache[item_id] = {
                "lower_set": {item_name, item_text, item_code, item_alias},
                "compact_set": {
                    _compact_alnum(item_name),
                    _compact_alnum(item_text),
                    _compact_alnum(item_code),
                    _compact_alnum(item_alias)
                }
            }
            
        pre = _suggestion_precompute_cache[item_id]
        if q in pre["lower_set"]:
            exact_name_items.append(item)
        elif q_compact and q_compact in pre["compact_set"]:
            exact_name_items.append(item)

    exact_payload = []
    if exact_name_items:
        exact_payload = _items_to_suggestion_payload(exact_name_items, limit=limit)


    # Seed suggestions from the richer search ranking first so exact and near-exact
    # product hits are available before we fall back to lightweight prefix scans.
    seeded_items = search(query, smart=False, brand=brand)
    seeded_payload = _items_to_suggestion_payload(seeded_items, limit=limit)
    query_code_meta = _parse_code_metadata(query)

    query_is_code = _is_code_or_model_query(query)
    exact_family_payload = []
    if query_is_code and (query_code_meta.get("full_compact") or query_code_meta.get("base_compact")):
        exact_family_items = []
        for item in stored_items:
            if not _is_supported_item(item):
                continue
            if not is_all_brand and _item_brand(item) != brand_lower:
                continue
            item_code_meta = _get_item_code_metadata(item)
            if query_code_meta.get("full_compact") and item_code_meta.get("full_compact") == query_code_meta["full_compact"]:
                exact_family_items.append(item)
                continue
            if (
                query_code_meta.get("base_compact")
                and item_code_meta.get("base_compact") == query_code_meta["base_compact"]
                and (
                    not query_code_meta.get("variant_compact")
                    or item_code_meta.get("variant_compact") == query_code_meta["variant_compact"]
                )
            ):
                exact_family_items.append(item)
        exact_family_payload = _items_to_suggestion_payload(exact_family_items, limit=limit)

    if query_is_code:
        exact_first = _merge_suggestion_payloads(exact_family_payload, seeded_payload, limit=limit)
        # We'll merge these into the final results instead of returning early


    # Split query into words but preserve codes like K-1234
    q_words = [w for w in re.split(r'\s+', q) if len(w) >= 2]
    # Add compacted components (k282, 1234) for better lookups
    tokens_to_check = set(q_words) | {q_compact}
    if len(q_compact) > 3:
        tokens_to_check.add(q_compact[:4])
    
    # Fast retrieval using sorted keyword list + bisect for O(log n) prefix lookup
    potential_indices = set()
    for w in tokens_to_check:
        if not w or len(w) < 2:
            continue
        wn = _normalize(w, strip_in=True)
        if not wn:
            continue
        # Direct hit first
        if wn in keyword_index:
            potential_indices.update(keyword_index[wn])
        # Bisect-based prefix scan (much faster than iterating all keys)
        if _keyword_keys_sorted:
            pos = bisect.bisect_left(_keyword_keys_sorted, wn)
            scanned = 0
            while pos < len(_keyword_keys_sorted) and scanned < 300:
                key = _keyword_keys_sorted[pos]
                if not key.startswith(wn):
                    break
                if key in keyword_index:
                    potential_indices.update(keyword_index[key])
                pos += 1
                scanned += 1
        if len(potential_indices) > 600:
            break

    suggestions = []
    seen = set()
    for seeded in seeded_payload:
        seen.add(
            f"{str(seeded.get('brand') or '').lower()}|{str(seeded.get('full_name') or seeded.get('text') or '').lower()}"
        )

    brand_lower = (brand or "").strip().lower()
    if brand_lower and brand_lower != "all" and not _is_supported_brand_name(brand_lower):
        return []
    is_all_brand = (not brand_lower) or (brand_lower == "all")

    # Also index with the full query as a compact token for direct matching
    q_compact = _compact_alnum(q)

    # Score and rank candidates
    for idx in potential_indices:
        item = stored_items[idx]
        if not _is_supported_item(item):
            continue
        
        if not is_all_brand:
            if _item_brand(item) != brand_lower:
                continue

        name = item.get("name", "")
        if not name: continue
        item_code_meta = _get_item_code_metadata(item)
        
        name_lower = name.lower()
        name_compact = _compact_alnum(name)
        
        # Simple scoring
        score = 0
        if q in name_lower: score += 400
        for w in q_words:
            if w in name_lower:
                score += 80
        if query_code_meta.get("base_compact") and item_code_meta.get("base_compact") == query_code_meta["base_compact"]:
            score += 30
        if query_code_meta.get("full_compact") and item_code_meta.get("full_compact") == query_code_meta["full_compact"]:
            score += 150 # Significantly boost exact code matches in suggestions
        if query_code_meta.get("variant_compact"):
            if item_code_meta.get("variant_compact") == query_code_meta["variant_compact"]:
                score += 25
            elif item_code_meta.get("variant_compact"):
                score -= 10

        # Boost items where the full query string appears in name (e.g. "450-1003" in "450-1003 G - Gold")
        if len(q) >= 3 and q in name_lower:
            score += 200
        if q_compact and len(q_compact) >= 3:
            if name_compact == q_compact or item_code_meta.get("full_compact") == q_compact:
                score += 5000 # SUPER MASSIVE boost for exact code match
            elif name_compact.startswith(q_compact):
                score += 2000 # Very high boost for prefix match
            elif q_compact in name_compact:
                score += 500

        if item.get("source") == "Manual Entry":
            score += 3000 # Massive boost for manually added items/images
            
        if item.get("brand") in {"Aquant", "Kohler"}:
            score += 1000 # Extreme boost for core brands
            
        score += _item_quality_bonus(item)
        
        # Use item name for display to preserve prefixes like "450-" that code parsing might separate
        name_parts = name.split(" - ", 1)
        display_text = _clean_display_text(name_parts[0].strip())
        if not display_text:
            display_text = _clean_display_text(item_code_meta.get("full_code") or name.split(" - ")[0].strip())
        full_display = _clean_display_text(name.strip())
        if not display_text: continue
        
        key = f"{str(item.get('brand') or '').lower()}|{full_display.lower()}"
        entry = {
            "score": score,
            "code": display_text,
            "full_name": full_display,
            "brand": item.get("brand", "Aquant"),
            "image_list": item.get("images", []),
            "item": item
        }
        if key not in seen:
            suggestions.append(entry)
            seen.add(key)
        else:
            for i, existing in enumerate(suggestions):
                existing_key = f"{str(existing.get('brand') or '').lower()}|{str(existing.get('full_name') or '').lower()}"
                if existing_key == key and score > existing.get("score", 0):
                    suggestions[i] = entry
                    break
        
        if len(suggestions) > max(80, limit * 3):
            break

    # Sort by score descending and then by full text length
    suggestions.sort(key=lambda x: (-x["score"], len(x["full_name"])))
    
    # 5. FINAL MERGE: Prioritize our custom-scored suggestions, then fill with seeded results
    # Convert suggestions to the standard payload format
    scored_payload = []
    for s in suggestions:
        full_name = s["full_name"]
        parts = full_name.split(" - ", 1)
        name_desc = _clean_display_text(parts[1].strip()) if len(parts) > 1 else ""
        display_item = prepare_item_for_display(s["item"])
        scored_payload.append({
            "text": _clean_display_text(s["code"]),
            "description": name_desc,
            "full_name": _clean_display_text(full_name),
            "display_name": display_item.get("display_name") or _clean_display_text(full_name),
            "display_code": display_item.get("display_code") or _clean_display_text(s["code"]),
            "brand": _clean_display_text(s["brand"]),
            "image": _best_item_image(s["item"]),
            "price": display_item.get("price"),
            "raw_item": display_item
        })

    # Prioritize: 1. Exact Name/Code matches, 2. Code family matches, 3. Ranked keyword matches, 4. Seeded results
    result = _merge_suggestion_payloads(exact_payload, exact_first if 'exact_first' in locals() else [], scored_payload, seeded_payload, limit=limit)

    # Store in cache; evict oldest entry when over capacity
    if len(_suggestion_cache) >= _SUGGESTION_CACHE_MAX:
        try:
            oldest = next(iter(_suggestion_cache))
            del _suggestion_cache[oldest]
        except StopIteration:
            pass
    _suggestion_cache[cache_key] = result
    return result
