print("--- BACKEND STARTING ---")
from dotenv import load_dotenv
load_dotenv()
print("Importing FastAPI...")
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
print("Importing shutil/os...")
import shutil
import os
import json
import time
import re
from datetime import datetime
from urllib.parse import urlparse
import httpx
print("Importing custom modules...")
from pdf_reader import extract_content, chunk_content
import search_engine
import cloud_storage
import mongodb
from email_service import send_email_with_attachment
from quotation import generate_quote
from app_paths import resolve_data_dir
print("Done with imports!")

from fastapi.staticfiles import StaticFiles

app = FastAPI()

import sys
is_frozen = getattr(sys, 'frozen', False)
EXE_DIR = os.path.dirname(os.path.abspath(sys.executable)) if is_frozen else os.path.dirname(os.path.abspath(__file__))
_MEIPASS = getattr(sys, '_MEIPASS', EXE_DIR)
BUNDLED_DIR = _MEIPASS
if is_frozen:
    possible_internal = os.path.join(_MEIPASS, "_internal")
    if os.path.isdir(possible_internal):
        BUNDLED_DIR = possible_internal

BASE_DIR = BUNDLED_DIR
DATA_DIR = resolve_data_dir(is_frozen, EXE_DIR)

STATIC_DIR = os.path.join(BUNDLED_DIR, "static")
STATIC_IMAGES_DIR = os.path.join(DATA_DIR, "static", "images")
# BUNDLED_IMAGES_DIR used for catalog products
BUNDLED_IMAGES_DIR = os.path.join(STATIC_DIR, "images")
REPO_IMAGES_DIR = os.path.join(EXE_DIR, "static", "images")

STATIC_QUOTES_DIR = os.path.join(DATA_DIR, "static", "quotes")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
QUOTES_HISTORY_DIR = os.path.join(DATA_DIR, "quotes_history")
QUOTATION_PDF_PATH = os.path.join(DATA_DIR, "quotation.pdf")

# Ensure writable dirs exist
for d in [STATIC_QUOTES_DIR, UPLOAD_DIR, QUOTES_HISTORY_DIR]:
    os.makedirs(d, exist_ok=True)

if os.getenv("RENDER") == "true":
    try:
        import shutil
        if os.path.exists(STATIC_IMAGES_DIR):
            print(f"Clearing persistent image cache at {STATIC_IMAGES_DIR} to force repo images...")
            shutil.rmtree(STATIC_IMAGES_DIR, ignore_errors=True)
    except Exception:
        pass

os.makedirs(STATIC_IMAGES_DIR, exist_ok=True)

def _resolve_case_insensitive_path(root_dir: str, relative_path: str) -> str:
    current = os.path.abspath(root_dir)
    parts = [part for part in str(relative_path or "").replace("\\", "/").split("/") if part and part != "."]

    for part in parts:
        direct_path = os.path.join(current, part)
        if os.path.exists(direct_path):
            current = direct_path
            continue

        try:
            entries = {entry.lower(): entry for entry in os.listdir(current)}
        except OSError:
            return ""

        matched_name = entries.get(part.lower())
        if not matched_name:
            return ""
        current = os.path.join(current, matched_name)

    return current if os.path.exists(current) else ""


def _find_image_path(filename: str) -> str:
    normalized = str(filename or "").strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return ""

    search_roots = []
    for root in (STATIC_IMAGES_DIR, BUNDLED_IMAGES_DIR, REPO_IMAGES_DIR):
        if root and root not in search_roots:
            search_roots.append(root)

    # First honor exact relative paths like Aquant/9272.png.
    for root in search_roots:
        resolved = _resolve_case_insensitive_path(root, normalized)
        if resolved:
            return resolved

    # Backward-compatible fallback: search by bare filename inside brand folders.
    if "/" not in normalized:
        target_name = normalized.lower()
        for root in search_roots:
            for current_root, _, files in os.walk(root):
                for current_file in files:
                    if current_file.lower() == target_name:
                        return os.path.join(current_root, current_file)

    return ""


# Helper for resolving image paths (prioritize writable uploads, fallback to bundled)
@app.get("/static/images/{filename:path}")
def serve_image(filename: str):
    resolved_path = _find_image_path(filename)
    if resolved_path:
        return FileResponse(resolved_path)

    raise HTTPException(status_code=404)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Enhanced CORS for desktop (allows null origin from file://)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production Electron, origin can be 'null'
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Quote-File-Url", "X-Quote-File-Name", "X-Quote-Number"],
)

# Optional: Log errors to file for debugging bundled app
import logging
log_file = os.path.join(DATA_DIR, "backend_errors.log")
try:
    logging.basicConfig(
        filename=log_file,
        level=logging.ERROR,
        format='%(asctime)s %(levelname)s:%(message)s',
    )
except OSError as e:
    print(f"Warning: file logging disabled: {e}")

import threading

def index_local_catalogs(force=False):
    # Helper to prevent multiple simultaneous indexes
    if getattr(index_local_catalogs, "_running", False):
        return
    index_local_catalogs._running = True

    try:
        import search_engine
        if not force and len(search_engine.stored_items) > 0:
            print("--- INDEX ALREADY LOADED, SKIPPING BACKGROUND SCAN ---")
            return

        _sync_cloud_catalogs_to_local()

        upload_dir = UPLOAD_DIR
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
            return

        files = [f for f in os.listdir(upload_dir) if f.lower().endswith(".pdf")]
        if not files:
            print("--- NO CATALOG PDF FOUND; KEEPING EXISTING INDEX ---")
            return

        print("--- BACKGROUND INDEXING START ---")
        search_engine.reset_index()  # Clean all stored data and AI vectors

        total_indexed = 0
        for filename in files:
            if "aquant" in filename.lower():
                brand = "Aquant"
            elif "kohler" in filename.lower():
                brand = "Kohler"
            else:
                continue

            path = os.path.join(upload_dir, filename)
            try:
                items = extract_content(path)
                # Set brand on all items before indexing
                for item in items:
                    if "brand" not in item or not item["brand"]:
                        item["brand"] = brand
                search_engine.add_to_index(None, items)
                total_indexed += len(items)
                print(f"Indexed: {len(items)} items from {filename} as {brand}")
            except Exception as e:
                print(f"Error indexing {filename}: {e}")
                import traceback
                traceback.print_exc()

        # Ensure index is saved
        search_engine.save_index()
        print(f"--- BACKGROUND INDEXING COMPLETE: {total_indexed} items indexed ---")
    finally:
        index_local_catalogs._running = False

def _bool_env(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, str(default))).strip().lower()
    return raw in {"1", "true", "yes", "on"}

def _normalize_whatsapp_number(raw_number: str) -> str:
    digits = "".join(ch for ch in str(raw_number or "") if ch.isdigit())
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"91{digits[1:]}"
    if len(digits) >= 12 and digits.startswith("91"):
        return digits
    return digits

def _sanitize_filename(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._")
    return cleaned or fallback

def _parse_cloud_timestamp(raw_value):
    if not raw_value:
        return time.time()
    text = str(raw_value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return time.time()

def _read_remote_bytes(url: str) -> bytes:
    try:
        response = httpx.get(url, timeout=60)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch remote file: {e}")

    if not response.is_success:
        raise HTTPException(status_code=404, detail="Remote file not found")

    return response.content

def _resolve_static_pdf_path(pdf_url: str):
    if not pdf_url:
        raise HTTPException(status_code=400, detail="Missing pdf_url")

    parsed = urlparse(pdf_url)
    raw_path = parsed.path if parsed.scheme else str(pdf_url)
    if not raw_path.startswith("/static/"):
        raise HTTPException(status_code=400, detail="pdf_url must point to /static/*")

    rel_path = raw_path.lstrip("/")
    static_root = os.path.abspath(STATIC_DIR)
    abs_path = os.path.abspath(os.path.normpath(os.path.join(BASE_DIR, rel_path)))

    # Prevent path traversal outside static folder.
    if not abs_path.startswith(static_root):
        raise HTTPException(status_code=400, detail="Invalid pdf_url path")

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="PDF file not found on server")

    return abs_path, os.path.basename(abs_path), raw_path

def _load_pdf_bytes(pdf_url: str, requested_name: str = ""):
    if cloud_storage.is_absolute_url(pdf_url):
        parsed = urlparse(pdf_url)
        detected_name = os.path.basename(parsed.path) or "quotation.pdf"
        return _read_remote_bytes(pdf_url), requested_name or detected_name

    pdf_path, detected_name, _ = _resolve_static_pdf_path(pdf_url)
    with open(pdf_path, "rb") as handle:
        return handle.read(), requested_name or detected_name


def _list_local_catalog_files():
    if not os.path.exists(UPLOAD_DIR):
        return []

    file_details = []
    for filename in os.listdir(UPLOAD_DIR):
        if not filename.lower().endswith(".pdf"):
            continue

        path = os.path.join(UPLOAD_DIR, filename)
        try:
            stat = os.stat(path)
        except OSError:
            continue

        file_details.append({
            "name": filename,
            "size": round(stat.st_size / (1024 * 1024), 2),
            "date": stat.st_mtime,
        })

    file_details.sort(key=lambda item: item["date"], reverse=True)
    return file_details

def _sync_cloud_catalogs_to_local():
    if not cloud_storage.is_enabled():
        return

    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        local_names = {
            filename
            for filename in os.listdir(UPLOAD_DIR)
            if filename.lower().endswith(".pdf")
        }
        remote_entries = [
            entry for entry in cloud_storage.list_objects(cloud_storage.CATALOGS_BUCKET)
            if str(entry.get("name") or "").lower().endswith(".pdf")
        ]
        remote_names = set()
        for entry in remote_entries:
            filename = str(entry.get("name") or "").strip()
            if not filename:
                continue

            remote_names.add(filename)
            local_path = os.path.join(UPLOAD_DIR, filename)
            if not os.path.exists(local_path):
                cloud_storage.download_to_path(cloud_storage.CATALOGS_BUCKET, filename, local_path)

        # Bootstrap bundled/local catalogs into cloud if the bucket is empty
        # or if the deployment still has seed PDFs that are not yet synced.
        for filename in sorted(local_names):
            if filename in remote_names:
                continue
            local_path = os.path.join(UPLOAD_DIR, filename)
            try:
                cloud_storage.upload_file(
                    cloud_storage.CATALOGS_BUCKET,
                    filename,
                    local_path,
                    "application/pdf",
                )
                remote_names.add(filename)
            except Exception as e:
                print(f"Warning: failed to bootstrap catalog '{filename}' to cloud: {e}")

        # Only delete local PDFs when cloud has a non-empty authoritative list.
        for filename in os.listdir(UPLOAD_DIR):
            if (
                remote_names
                and filename.lower().endswith(".pdf")
                and filename not in remote_names
            ):
                try:
                    os.remove(os.path.join(UPLOAD_DIR, filename))
                except OSError:
                    pass
    except Exception as e:
        print(f"Warning: failed to sync cloud catalogs locally: {e}")

def _bool_env(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, str(default))).strip().lower()
    return raw in {"1", "true", "yes", "on"}

def _normalize_whatsapp_number(raw_number: str) -> str:
    digits = "".join(ch for ch in str(raw_number or "") if ch.isdigit())
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"91{digits[1:]}"
    if len(digits) >= 12 and digits.startswith("91"):
        return digits
    return digits

def _sanitize_filename(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._")
    return cleaned or fallback

def _parse_cloud_timestamp(raw_value):
    if not raw_value:
        return time.time()
    text = str(raw_value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return time.time()

def _read_remote_bytes(url: str) -> bytes:
    try:
        response = httpx.get(url, timeout=60)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch remote file: {e}")

    if not response.is_success:
        raise HTTPException(status_code=404, detail="Remote file not found")

    return response.content

def _resolve_static_pdf_path(pdf_url: str):
    if not pdf_url:
        raise HTTPException(status_code=400, detail="Missing pdf_url")

    parsed = urlparse(pdf_url)
    raw_path = parsed.path if parsed.scheme else str(pdf_url)
    if not raw_path.startswith("/static/"):
        raise HTTPException(status_code=400, detail="pdf_url must point to /static/*")

    rel_path = raw_path.lstrip("/")
    static_root = os.path.abspath(STATIC_DIR)
    abs_path = os.path.abspath(os.path.normpath(os.path.join(BASE_DIR, rel_path)))

    # Prevent path traversal outside static folder.
    if not abs_path.startswith(static_root):
        raise HTTPException(status_code=400, detail="Invalid pdf_url path")

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="PDF file not found on server")

    return abs_path, os.path.basename(abs_path), raw_path

def _load_pdf_bytes(pdf_url: str, requested_name: str = ""):
    if cloud_storage.is_absolute_url(pdf_url):
        parsed = urlparse(pdf_url)
        detected_name = os.path.basename(parsed.path) or "quotation.pdf"
        return _read_remote_bytes(pdf_url), requested_name or detected_name

    pdf_path, detected_name, _ = _resolve_static_pdf_path(pdf_url)
    with open(pdf_path, "rb") as handle:
        return handle.read(), requested_name or detected_name


def _list_local_catalog_files():
    if not os.path.exists(UPLOAD_DIR):
        return []

    file_details = []
    for filename in os.listdir(UPLOAD_DIR):
        if not filename.lower().endswith(".pdf"):
            continue

        path = os.path.join(UPLOAD_DIR, filename)
        try:
            stat = os.stat(path)
        except OSError:
            continue

        file_details.append({
            "name": filename,
            "size": round(stat.st_size / (1024 * 1024), 2),
            "date": stat.st_mtime,
        })

    file_details.sort(key=lambda item: item["date"], reverse=True)
    return file_details

def _sync_cloud_catalogs_to_local():
    if not cloud_storage.is_enabled():
        return

    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        local_names = {
            filename
            for filename in os.listdir(UPLOAD_DIR)
            if filename.lower().endswith(".pdf")
        }
        remote_entries = [
            entry for entry in cloud_storage.list_objects(cloud_storage.CATALOGS_BUCKET)
            if str(entry.get("name") or "").lower().endswith(".pdf")
        ]
        remote_names = set()
        for entry in remote_entries:
            filename = str(entry.get("name") or "").strip()
            if not filename:
                continue

            remote_names.add(filename)
            local_path = os.path.join(UPLOAD_DIR, filename)
            if not os.path.exists(local_path):
                cloud_storage.download_to_path(cloud_storage.CATALOGS_BUCKET, filename, local_path)

        # Bootstrap bundled/local catalogs into cloud if the bucket is empty
        # or if the deployment still has seed PDFs that are not yet synced.
        for filename in sorted(local_names):
            if filename in remote_names:
                continue
            local_path = os.path.join(UPLOAD_DIR, filename)
            try:
                cloud_storage.upload_file(
                    cloud_storage.CATALOGS_BUCKET,
                    filename,
                    local_path,
                    "application/pdf",
                )
                remote_names.add(filename)
            except Exception as e:
                print(f"Warning: failed to bootstrap catalog '{filename}' to cloud: {e}")

        # Only delete local PDFs when cloud has a non-empty authoritative list.
        for filename in os.listdir(UPLOAD_DIR):
            if (
                remote_names
                and filename.lower().endswith(".pdf")
                and filename not in remote_names
            ):
                try:
                    os.remove(os.path.join(UPLOAD_DIR, filename))
                except OSError:
                    pass
    except Exception as e:
        print(f"Warning: failed to sync cloud catalogs locally: {e}")

def _save_quote_record(filename: str, data: dict):
    if mongodb.is_enabled():
        try:
            mongodb.save_quote(filename, data)
        except Exception as e:
            print(f"Warning: failed to save to MongoDB: {e}")

    os.makedirs(QUOTES_HISTORY_DIR, exist_ok=True)
    local_path = os.path.join(QUOTES_HISTORY_DIR, filename)
    with open(local_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)

    if cloud_storage.is_enabled():
        try:
            cloud_storage.upload_bytes(
                cloud_storage.QUOTE_HISTORY_BUCKET,
                filename,
                json.dumps(data, ensure_ascii=False).encode("utf-8"),
                "application/json",
            )
        except Exception as e:
            print(f"Warning: failed to sync quote history to cloud: {e}")

def _list_quote_records():
    if mongodb.is_enabled():
        try:
            return mongodb.list_quotes()
        except Exception as e:
            print(f"Warning: failed to list MongoDB quotes: {e}")

    if cloud_storage.is_enabled():
        try:
            details = []
            for entry in cloud_storage.list_objects(cloud_storage.QUOTE_HISTORY_BUCKET):
                filename = str(entry.get("name") or "").strip()
                if not filename.lower().endswith(".json"):
                    continue

                raw = cloud_storage.download_bytes(cloud_storage.QUOTE_HISTORY_BUCKET, filename)
                if not raw:
                    continue

                content = json.loads(raw.decode("utf-8"))
                details.append({
                    "id": filename,
                    "client": content.get("client_name", "N/A"),
                    "total": content.get("grand_total", 0),
                    "date": _parse_cloud_timestamp(entry.get("updated_at") or entry.get("created_at")),
                })

            details.sort(key=lambda item: item["date"], reverse=True)
            return details
        except Exception as e:
            print(f"Warning: failed to list cloud quote history: {e}")

    folder = QUOTES_HISTORY_DIR
    if not os.path.exists(folder):
        return []

    files = [f for f in os.listdir(folder) if f.endswith(".json")]
    details = []
    for filename in files:
        path = os.path.join(folder, filename)
        stat = os.stat(path)
        with open(path, "r", encoding="utf-8") as handle:
            try:
                content = json.load(handle)
                details.append({
                    "id": filename,
                    "client": content.get("client_name", "N/A"),
                    "total": content.get("grand_total", 0),
                    "date": stat.st_mtime,
                })
            except Exception:
                continue

    details.sort(key=lambda item: item["date"], reverse=True)
    return details

def _load_quote_record(quote_id: str):
    if mongodb.is_enabled():
        try:
            doc = mongodb.load_quote(quote_id)
            if doc is not None:
                return doc
        except Exception as e:
            print(f"Warning: failed to load from MongoDB: {e}")

    if cloud_storage.is_enabled():
        try:
            raw = cloud_storage.download_bytes(cloud_storage.QUOTE_HISTORY_BUCKET, quote_id)
            if raw is not None:
                return json.loads(raw.decode("utf-8"))
        except Exception as e:
            print(f"Warning: failed to load cloud quote '{quote_id}': {e}")

    path = os.path.join(QUOTES_HISTORY_DIR, quote_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return None

def _delete_quote_record(quote_id: str) -> bool:
    deleted = False
    if mongodb.is_enabled():
        try:
            deleted = mongodb.delete_quote(quote_id)
        except Exception as e:
            print(f"Warning: failed to delete from MongoDB: {e}")

    path = os.path.join(QUOTES_HISTORY_DIR, quote_id)
    if os.path.exists(path):
        os.remove(path)
        deleted = True

    if cloud_storage.is_enabled():
        try:
            cloud_storage.delete_object(cloud_storage.QUOTE_HISTORY_BUCKET, quote_id)
            deleted = True
        except Exception as e:
            print(f"Warning: failed to delete cloud quote '{quote_id}': {e}")

    return deleted

@app.on_event("startup")
async def startup_event():
    def warm_catalog_index():
        try:
            import search_engine
            _sync_cloud_catalogs_to_local()

            if not search_engine.load_index() or not search_engine.stored_items:
                print("No usable saved index found; rebuilding from local uploads...")
                index_local_catalogs(force=True)
            else:
                print("Using saved search index.")

            # On Render: load search index FROM MongoDB (do NOT overwrite it)
            if os.getenv("RENDER") == "true" and mongodb.is_enabled():
                try:
                    _mongo_data = mongodb.load_search_index()
                    if _mongo_data and _mongo_data.get("stored_items"):
                        search_engine.stored_items = _mongo_data.get("stored_items", [])
                        search_engine.keyword_index = _mongo_data.get("keyword_index", {})
                        search_engine._suggestion_cache.clear()
                        search_engine.item_code_meta_cache.clear()
                        print(f"Render startup: Loaded {len(search_engine.stored_items)} items FROM MongoDB.")
                    else:
                        print("Render startup: MongoDB index empty, keeping bundled index.")
                except Exception as _e:
                    print(f"Warning: Render startup MongoDB load failed: {_e}")

        except Exception as e:
            print(f"Warning: background startup warmup failed: {e}")

    threading.Thread(target=warm_catalog_index, daemon=True).start()


@app.get("/admin/force-mongo-sync")
async def force_mongo_sync(secret: str = ""):
    """Force-push the bundled search_index_v2.json to MongoDB. Pass ?secret=sync123 to authorize."""
    if secret != "sync123":
        raise HTTPException(status_code=403, detail="Unauthorized")
    import search_engine
    bundled_index = search_engine.INDEX_FILE_BUNDLED
    if not os.path.exists(bundled_index):
        raise HTTPException(status_code=404, detail="Bundled index not found")
    try:
        with open(bundled_index, "r", encoding="utf-8") as f:
            data = json.load(f)
        mongodb.save_search_index(data)
        count = len(data.get("stored_items", []))
        # Also reload in-memory index
        search_engine.stored_items = data.get("stored_items", [])
        search_engine.keyword_index = data.get("keyword_index", {})
        search_engine._suggestion_cache.clear()
        search_engine.item_code_meta_cache.clear()
        return {"message": f"MongoDB synced successfully with {count} items.", "items": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    return {
        "service": "quotation-ai-backend",
        "status": "ok",
        "docs": "/docs",
        "health": "/status",
    }


@app.get("/refresh")
async def refresh_catalogs():
    import search_engine
    # Try to load from MongoDB first (latest data)
    if mongodb.is_enabled():
        try:
            _mongo_data = mongodb.load_search_index()
            if _mongo_data and _mongo_data.get("stored_items"):
                search_engine.stored_items = _mongo_data.get("stored_items", [])
                search_engine.keyword_index = _mongo_data.get("keyword_index", {})
                search_engine._suggestion_cache.clear()
                search_engine.item_code_meta_cache.clear()
                return {"message": f"Index reloaded from MongoDB with {len(search_engine.stored_items)} items."}
        except Exception as e:
            print(f"Warning: MongoDB refresh failed, falling back to disk: {e}")
    search_engine.load_index(force=True)
    search_engine._suggestion_cache.clear()
    search_engine.item_code_meta_cache.clear()
    return {"message": "Index reloaded from disk."}

@app.get("/debug")
def debug_paths():
    import search_engine
    return {"bundled": search_engine.INDEX_FILE_BUNDLED, "persistent": search_engine.INDEX_FILE_PERSISTENT, "items": len(search_engine.stored_items)}

@app.get("/eval")
def eval_code(code: str):
    import search_engine
    try:
        res = eval(code, {"search_engine": search_engine, "app": app})
        return {"result": str(res)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/status")
def get_status():
    import search_engine
    if not search_engine.stored_items:
        try:
            search_engine.load_index()
        except Exception as e:
            print(f"Warning: failed to load search index during status check: {e}")
    total = len(search_engine.stored_items)
    samples = []
    for item in search_engine.stored_items[:5]:
        samples.append({
            "text": item["text"][:100], 
            "page": item["page"],
            "source": item.get("source", "N/A")
        })
    return {
        "indexed_items": total,
        "faiss_ready": search_engine.vector_index is not None,
        "catalog_files": len(_list_local_catalog_files()),
        "sample_items": samples
    }




@app.post("/generate-quote")
async def create_quote(data: dict):
    timestamp = int(time.time())
    client_slug = _sanitize_filename(data.get("client_name", "Unknown"), "Unknown")
    quote_payload = dict(data)

    # Auto-generate a readable quotation number: SC-YYYYMMDD-XXXX
    date_str = datetime.now().strftime("%Y%m%d")
    seq = str(timestamp)[-4:]          # last 4 digits of unix timestamp
    quote_number = f"SC-{date_str}-{seq}"
    quote_payload["quote_number"] = quote_number
    quote_payload["output_path"] = QUOTATION_PDF_PATH

    filename = f"quote_{timestamp}_{client_slug}.json"
    _save_quote_record(filename, quote_payload)

    generate_quote(quote_payload)

    share_pdf_name = f"quote_{timestamp}_{client_slug}.pdf"
    share_pdf_url = ""

    if cloud_storage.is_enabled():
        try:
            share_pdf_url = cloud_storage.upload_file(
                cloud_storage.QUOTES_BUCKET,
                share_pdf_name,
                QUOTATION_PDF_PATH,
                "application/pdf",
            )
        except Exception as e:
            print(f"Warning: failed to sync quote PDF to cloud: {e}")

    if not share_pdf_url:
        os.makedirs(STATIC_QUOTES_DIR, exist_ok=True)
        share_pdf_path = os.path.join(STATIC_QUOTES_DIR, share_pdf_name)
        shutil.copyfile(QUOTATION_PDF_PATH, share_pdf_path)
        share_pdf_url = f"/static/quotes/{share_pdf_name}"

    return FileResponse(
        QUOTATION_PDF_PATH,
        media_type="application/pdf",
        filename="quotation.pdf",
        headers={
            "X-Quote-File-Url":    share_pdf_url,
            "X-Quote-File-Name":   share_pdf_name,
            "X-Quote-Number":      quote_number,
        },
    )

@app.post("/send-quote-email")
async def send_quote_email(data: dict):
    to_email = str(data.get("to_email") or "").strip()
    subject = str(data.get("subject") or "Quotation PDF").strip()
    body = str(data.get("body") or "").strip()
    pdf_url = str(data.get("pdf_url") or "").strip()
    requested_name = str(data.get("pdf_filename") or "").strip()

    if not to_email:
        raise HTTPException(status_code=400, detail="Recipient email is required")

    pdf_bytes, pdf_name = _load_pdf_bytes(pdf_url, requested_name)

    try:
        send_email_with_attachment(to_email, subject, body, pdf_bytes, pdf_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email send failed: {e}")

    return {"message": "Email sent with PDF attachment"}

@app.post("/send-quote-whatsapp")
async def send_quote_whatsapp(data: dict):
    raw_to = str(data.get("to_number") or "").strip()
    body = str(data.get("body") or "").strip()
    second_message = str(data.get("second_message") or "").strip()
    pdf_url = str(data.get("pdf_url") or "").strip()
    requested_name = str(data.get("pdf_filename") or "").strip()

    to_number = _normalize_whatsapp_number(raw_to)
    if not to_number:
        raise HTTPException(status_code=400, detail="Valid WhatsApp number is required")

    token = os.getenv("WHATSAPP_TOKEN", "").strip()
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    if not token or not phone_number_id:
        raise HTTPException(
            status_code=500,
            detail="WhatsApp API not configured: set WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID",
        )

    pdf_bytes, pdf_name = _load_pdf_bytes(pdf_url, requested_name)

    base_url = f"https://graph.facebook.com/v20.0/{phone_number_id}"
    auth_headers = {"Authorization": f"Bearer {token}"}

    try:
        # MESSAGE 1: Send detailed text first.
        if body:
            text_payload = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"body": body[:4000]},
            }
            text_res = httpx.post(
                f"{base_url}/messages",
                headers={**auth_headers, "Content-Type": "application/json"},
                json=text_payload,
                timeout=45,
            )
            if not text_res.is_success:
                raise HTTPException(status_code=500, detail=f"WhatsApp text send failed: {text_res.text}")

        # Upload document media.
        files = {"file": (pdf_name, pdf_bytes, "application/pdf")}
        media_payload = {"messaging_product": "whatsapp", "type": "application/pdf"}
        media_res = httpx.post(
            f"{base_url}/media",
            headers=auth_headers,
            data=media_payload,
            files=files,
            timeout=60,
        )
        if not media_res.is_success:
            raise HTTPException(status_code=500, detail=f"WhatsApp media upload failed: {media_res.text}")

        media_id = (media_res.json() or {}).get("id")
        if not media_id:
            raise HTTPException(status_code=500, detail="WhatsApp media upload failed: no media id returned")

        # MESSAGE 2: Send uploaded PDF as document.
        doc_payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "document",
            "document": {
                "id": media_id,
                "filename": pdf_name,
                "caption": "Quotation PDF attached.",
            },
        }
        doc_res = httpx.post(
            f"{base_url}/messages",
            headers={**auth_headers, "Content-Type": "application/json"},
            json=doc_payload,
            timeout=45,
        )
        if not doc_res.is_success:
            raise HTTPException(status_code=500, detail=f"WhatsApp document send failed: {doc_res.text}")

        # MESSAGE 3: Send second text message if provided (PDF link, notes, etc)
        if second_message:
            second_payload = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"body": second_message[:4000]},
            }
            second_res = httpx.post(
                f"{base_url}/messages",
                headers={**auth_headers, "Content-Type": "application/json"},
                json=second_payload,
                timeout=45,
            )
            if not second_res.is_success:
                raise HTTPException(status_code=500, detail=f"WhatsApp second message send failed: {second_res.text}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WhatsApp send failed: {e}")

    return {"message": "WhatsApp sent: Message 1 + PDF + Message 2"}

@app.get("/list-quotes")
def list_quotes():
    return {"quotes": _list_quote_records()}

@app.get("/get-quote/{id}")
def get_quote(id: str):
    record = _load_quote_record(id)
    if record is not None:
        return record
    raise HTTPException(status_code=404)

@app.delete("/delete-quote/{id}")
def delete_quote(id: str):
    if _delete_quote_record(id):
        return {"message": "Deleted"}
    raise HTTPException(status_code=404)



@app.get("/search")
def search_item(q: str, brand: str = None, smart: bool = False, exact: bool = False):
    # Handle "all" brand from frontend if it slips through
    if brand == "all": brand = None
    if exact:
        results = search_engine.search_exact(q, smart=smart, brand=brand)
    else:
        results = search_engine.search(q, smart=smart, brand=brand)
    return {"results": results}

@app.get("/search-suggestions")
def search_suggestions(q: str, brand: str = None):
    from fastapi.responses import JSONResponse
    import traceback
    try:
        if brand == "all": brand = None
        suggestions = search_engine.get_suggestions(q, brand=brand)
        return JSONResponse(
            content={"suggestions": suggestions},
            headers={"Cache-Control": "max-age=30, stale-while-revalidate=60"},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()}
        )


@app.post("/catalog/add")
async def add_manual_item(
    name: str = Form(...),
    price: str = Form(...),
    brand: str = Form(...),
    category: str = Form(""),
    file: UploadFile = File(None)
):
    import search_engine
    if str(brand or "").strip().lower() not in search_engine.SUPPORTED_BRANDS:
        raise HTTPException(status_code=400, detail="Only Aquant and Kohler items are allowed")
    
    image_path = None
    if file:
        dest_dir = os.path.join(STATIC_IMAGES_DIR, "manual")
        os.makedirs(dest_dir, exist_ok=True)
        img_filename = f"manual_{int(time.time())}_{_sanitize_filename(file.filename, 'image.jpg')}"
        dest_path = os.path.join(dest_dir, img_filename)
        
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        image_path = f"/static/images/manual/{img_filename}"
        if cloud_storage.is_enabled():
            try:
                image_path = cloud_storage.upload_file(
                    cloud_storage.PRODUCT_IMAGES_BUCKET,
                    f"manual/{img_filename}",
                    dest_path,
                    cloud_storage.guess_content_type(img_filename, "image/jpeg"),
                )
            except Exception as e:
                print(f"Warning: failed to sync manual image to cloud: {e}")
        
    new_item = {
        "text": f"{name}\nMRP : ` {price}/-",
        "name": name,
        "price": price,
        "page": 0,
        "source": "Manual Entry",
        "images": [image_path] if image_path else [],
        "brand": brand,
        "category": category
    }
    
    search_engine.add_to_index(None, [new_item])
    search_engine.save_index()
    
    return {"message": "Success", "item": new_item}
@app.get("/ask")
def ask_question(q: str):
    # SMART mode for deep analysis
    results = search_engine.search(q, smart=True)
    if not results:
        return {"answer": "No results found in the catalog for your query."}
    
    # Just return a summary of the top result so it doesn't flood the UI with details
    top_result_text = results[0]["text"].replace("\n", " ").strip()
    if len(top_result_text) > 150:
        top_result_text = top_result_text[:150] + "..."
        
    answer = f"Top match from catalog:\nâ€¢ {top_result_text}\n(See exact match details in the cards below)"
    return {"answer": answer}



@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        safe_name = _sanitize_filename(file.filename, "catalog.pdf")
        path = os.path.join(UPLOAD_DIR, safe_name)
        content = await file.read()
        with open(path, "wb") as buffer:
            buffer.write(content)

        if cloud_storage.is_enabled():
            try:
                cloud_storage.upload_bytes(
                    cloud_storage.CATALOGS_BUCKET,
                    safe_name,
                    content,
                    "application/pdf",
                )
            except Exception as e:
                print(f"Warning: failed to sync catalog to cloud: {e}")

        # Run indexing in background - don't block the response
        threading.Thread(target=index_local_catalogs, args=(True,), daemon=True).start()
        return {"message": f"'{safe_name}' uploaded! Indexing in background..."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list-uploads")
def list_uploads():
    if cloud_storage.is_enabled():
        try:
            file_details = []
            for entry in cloud_storage.list_objects(cloud_storage.CATALOGS_BUCKET):
                filename = str(entry.get("name") or "").strip()
                if not filename.lower().endswith(".pdf"):
                    continue

                metadata = entry.get("metadata") or {}
                raw_size = metadata.get("size") or entry.get("size") or 0
                try:
                    size_mb = round(int(raw_size) / (1024 * 1024), 2)
                except Exception:
                    size_mb = 0

                file_details.append({
                    "name": filename,
                    "size": size_mb,
                    "date": _parse_cloud_timestamp(entry.get("updated_at") or entry.get("created_at")),
                })

            file_details.sort(key=lambda item: item["date"], reverse=True)
            if file_details:
                return {"files": file_details}
        except Exception as e:
            print(f"Warning: failed to list cloud uploads: {e}")

    return {"files": _list_local_catalog_files()}

@app.delete("/delete-upload/{filename}")
def delete_upload(filename: str):
    path = os.path.join(UPLOAD_DIR, filename)
    deleted = False
    if os.path.exists(path):
        os.remove(path)
        deleted = True

    if cloud_storage.is_enabled():
        try:
            cloud_storage.delete_object(cloud_storage.CATALOGS_BUCKET, filename)
            deleted = True
        except Exception as e:
            print(f"Warning: failed to delete cloud upload '{filename}': {e}")

    if deleted:
        # Re-index in background after deletion
        threading.Thread(target=index_local_catalogs, args=(True,), daemon=True).start()
        return {"message": f"'{filename}' deleted and system re-indexed."}
    raise HTTPException(status_code=404, detail="File not found")


@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    try:
        ext = os.path.splitext(file.filename)[1]
        if not ext:
            ext = ".png"
        safe_name = f"manual_{int(datetime.now().timestamp())}_{_sanitize_filename(file.filename, 'image' + ext)}"
        upload_dir = os.path.join(STATIC_DIR, "images", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        path = os.path.join(upload_dir, safe_name)
        content = await file.read()
        with open(path, "wb") as buffer:
            buffer.write(content)
        return {"url": f"/static/images/uploads/{safe_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rename-upload")
def rename_upload(data: dict):
    old_name = data.get("old_name")
    new_name = _sanitize_filename(data.get("new_name"), "")
    
    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="Missing names")
        
    old_path = os.path.join(UPLOAD_DIR, old_name)
    new_path = os.path.join(UPLOAD_DIR, new_name)

    if os.path.exists(new_path):
        raise HTTPException(status_code=400, detail="New filename already exists")

    renamed = False
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        renamed = True

    if cloud_storage.is_enabled():
        try:
            cloud_storage.move_object(cloud_storage.CATALOGS_BUCKET, old_name, new_name)
            renamed = True
        except Exception as e:
            print(f"Warning: failed to rename cloud upload '{old_name}' -> '{new_name}': {e}")

    if not renamed:
        raise HTTPException(status_code=404, detail="Original file not found")

    # Re-index in background after rename
    threading.Thread(target=index_local_catalogs, args=(True,), daemon=True).start()
    return {"message": f"Renamed to {new_name}"}

@app.get("/catalog/index")
def get_catalog_index():
    import search_engine
    import re
    
    # Check cache first for instant loading
    if search_engine.catalog_summary_cache:
        return search_engine.catalog_summary_cache
        
    if not search_engine.stored_items:
        search_engine.load_index()
    
    if not search_engine.stored_items:
        return []
        
    brand_map = {}
    # Iterate through all items just once and build the summary
    for item in search_engine.stored_items:
        brand = item.get("brand")
        if not brand:
            src = str(item.get("source") or "Generic").lower()
            brand = "Kohler" if "kohler" in src else "Aquant" if "aquant" in src else "Generic"

        if str(brand or "").strip().lower() not in search_engine.SUPPORTED_BRANDS:
            continue
        
        if brand not in brand_map:
            brand_map[brand] = {"name": brand, "collections": set()}
            
        # Use the 'category' field if available
        h = item.get("category")
        if h:
            brand_map[brand]["collections"].add(h)
        else:
            # Fallback for older indexed items or undetected headers
            first_line = ""
            if "text" in item:
                first_line = item["text"].split("\n")[0].strip()
            heading_match = re.match(r'^([A-Z\s]{4,28})', first_line)
            if heading_match:
                h = heading_match.group(1).strip()
                if len(h) > 3:
                    brand_map[brand]["collections"].add(h)

    result = []
    # Always prioritize the big two for display
    for b_name in ["Aquant", "Kohler"]:
       if b_name in brand_map:
            b_data = brand_map.pop(b_name)
            cols = sorted(list(b_data["collections"])) or ["Standard Products"]
            result.append({"brand": b_name, "collections": cols[:25]})

    # Save to cache
    search_engine.catalog_summary_cache = result
    return result

@app.get("/catalog/browse")
def browse_collection(brand: str, collection: str = None):
    import search_engine
    if str(brand or "").strip().lower() not in search_engine.SUPPORTED_BRANDS:
        return {"results": []}

    results = []
    brand_lower = brand.lower()
    collection_lower = (collection or "").lower()
    
    for item in search_engine.stored_items:
        item_brand = search_engine._item_brand(item)
        if item_brand != brand_lower or not search_engine._is_supported_item(item):
            continue
            
        # Collection / Category check
        if not collection or collection == "All Products" or collection == "Standard Products":
            results.append(item)
        else:
            item_cat = str(item.get("category", "")).lower()
            item_text = item.get("text", "").lower()

            # Kohler dashboard has fixed sections; use semantic fallbacks for empty categories.
            if brand_lower == "kohler" and collection_lower == "toilets":
                toilet_cats = {
                    "toilets",
                    "smart toilets & bidet seats",
                    "1 pc toilets & wall hungs",
                    "in-wall tanks",
                }
                if item_cat in toilet_cats or any(k in item_text for k in ["toilet", "bidet", "cleansing seat"]):
                    results.append(item)
            elif brand_lower == "kohler" and collection_lower == "in-wall tanks":
                if ("wall" in item_cat and "tank" in item_cat) or any(
                    k in item_text for k in ["in-wall", "concealed tank", "concealed cistern", "dual flush tank", "tank only"]
                ):
                    results.append(item)
            elif brand_lower == "kohler" and collection_lower == "cleaning solutions":
                if item_cat == "cleaning solutions" or any(k in item_text for k in ["cleaner", "cleaning solution", "descaler"]):
                    results.append(item)
            elif collection_lower in item_cat:
                results.append(item)
            elif not item_cat and collection_lower in item_text:
                # Only fall back to raw text when the parser could not assign a category.
                results.append(item)
            
        if len(results) >= 500:
            break
    
    return {"results": search_engine.prepare_items_for_display(results)}


if __name__ == "__main__":
    import uvicorn
    try:
        print("Starting Uvicorn...")
        uvicorn.run(app, host="0.0.0.0", port=8000, http="h11", loop="asyncio")
    except Exception as e:
        import traceback
        error_msg = f"FATAL ERROR during backend startup: {e}\n{traceback.format_exc()}"
        print(error_msg)
        try:
            with open(log_file, "a") as f:
                f.write(f"\n{datetime.now()} {error_msg}\n")
        except:
            pass
        sys.exit(1)







