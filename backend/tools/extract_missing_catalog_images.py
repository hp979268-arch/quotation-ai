import json
import os
import re
import sys
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "search_index_v2.json"
AQUANT_PDF = ROOT / "uploads" / "Aquant Price List Vol 15. Feb 2026_Searchable.pdf"
KOHLER_PDF = ROOT / "uploads" / "Kohler_Pricebook (March'26).pdf"

sys.path.insert(0, str(ROOT))
import search_engine  # noqa: E402


def _preferred_code_text(item, brand: str) -> str:
    search_code = str(item.get("search_code") or "").strip()
    name = str(item.get("name") or "").strip()

    if brand == "kohler":
        candidates = []
        for source in (search_code, name):
            candidates.extend(re.findall(r"K-\d[A-Z0-9-]*(?:\s+[A-Z0-9]+)?", source.upper()))
        if candidates:
            cleaned = []
            for candidate in candidates:
                candidate = re.sub(r"\s+", "-", candidate.strip())
                cleaned.append(candidate)
            cleaned.sort(key=len, reverse=True)
            return cleaned[0]

    return search_code or name


def _sanitize_filename(code: str) -> str:
    text = str(code or "").strip().upper()
    text = text.replace(" / ", "/").replace(" + ", "+")
    text = re.sub(r"\s+", "", text)
    text = text.replace("/", "-")
    text = re.sub(r"[^A-Z0-9+\-_]", "", text)
    return text.strip("-_") or "ITEM"


def _item_brand(item) -> str:
    return str(item.get("brand") or "").strip().lower()


def _pdf_for_brand(brand: str) -> Path | None:
    if brand == "aquant":
        return AQUANT_PDF
    if brand == "kohler":
        return KOHLER_PDF
    return None


def _image_dir_for_brand(brand: str) -> Path:
    if brand == "aquant":
        return ROOT / "static" / "images" / "Aquant"
    if brand == "kohler":
        return ROOT / "static" / "images" / "Kohler"
    raise ValueError(f"Unsupported brand: {brand}")


def _candidate_text_queries(item) -> list[str]:
    queries = []
    for raw in (
        item.get("search_code"),
        item.get("base_code"),
        item.get("full_code"),
        str(item.get("name") or "").split(" - ", 1)[0].strip(),
    ):
        value = str(raw or "").strip()
        if not value or value in queries:
            continue
        queries.append(value)

    search_code = str(item.get("search_code") or "").strip()
    if search_code:
        base = search_code.split()[0].strip()
        if base and base not in queries:
            queries.append(base)
        if "/" in search_code:
            for part in search_code.split("/"):
                part = part.strip()
                if part and part not in queries:
                    queries.append(part)

    if _item_brand(item) == "kohler":
        name = str(item.get("name") or "")
        embedded_codes = re.findall(r"K-\d[A-Z0-9-]*", name.upper())
        for code in embedded_codes:
            if code not in queries:
                queries.append(code)

    return queries


def _find_text_rect(page: fitz.Page, item) -> fitz.Rect | None:
    queries = _candidate_text_queries(item)
    for query in queries:
        rects = page.search_for(query)
        if rects:
            return rects[0]
    return None


def _image_blocks(page: fitz.Page) -> list[fitz.Rect]:
    blocks = []
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        if block.get("type") != 1:
            continue
        rect = fitz.Rect(block["bbox"])
        area = rect.get_area()
        if area < 1200:
            continue
        blocks.append(rect)
    return blocks


def _pick_best_rect(text_rect: fitz.Rect | None, image_rects: list[fitz.Rect]) -> fitz.Rect | None:
    if not image_rects:
        return None
    if text_rect is None:
        return max(image_rects, key=lambda rect: rect.get_area())

    tx = text_rect.x0 + text_rect.width / 2
    ty = text_rect.y0 + text_rect.height / 2

    def score(rect: fitz.Rect):
        ix = rect.x0 + rect.width / 2
        iy = rect.y0 + rect.height / 2
        dx = abs(ix - tx)
        dy = abs(iy - ty)
        # Prefer images above or near the text, but still allow side-by-side layouts.
        vertical_penalty = 0 if iy <= ty + 60 else (iy - ty) * 2.5
        return dx + dy + vertical_penalty - (rect.get_area() / 5000.0)

    return min(image_rects, key=score)


def _render_rect(page: fitz.Page, rect: fitz.Rect, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        return
    zoom = 3.2 if max(rect.width, rect.height) < 180 else 2.8
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
    pix.save(str(output_path))


def _page_candidates(item) -> list[int]:
    raw_page = item.get("page")
    if raw_page is None:
        return []
    try:
        base = int(raw_page)
    except (TypeError, ValueError):
        return []
    candidates = []
    for value in (base, base - 1, base + 1):
        if value not in candidates and value >= 0:
            candidates.append(value)
    return candidates


def _extract_for_item(doc: fitz.Document, item, brand: str) -> str | None:
    image_dir = _image_dir_for_brand(brand)
    output_name = f"{_sanitize_filename(_preferred_code_text(item, brand))}.png"
    output_path = image_dir / output_name
    public_path = f"/static/images/{image_dir.name}/{output_name}"

    page_numbers = [p for p in _page_candidates(item) if p < len(doc)]
    if not page_numbers:
        page_numbers = list(range(len(doc)))

    best_candidate = None
    for page_num in page_numbers:
        page = doc[page_num]
        rects = _image_blocks(page)
        if not rects:
            continue
        text_rect = _find_text_rect(page, item)
        chosen = _pick_best_rect(text_rect, rects)
        if chosen is None:
            continue

        candidate = {
            "page_num": page_num,
            "rect": chosen,
            "text_rect": text_rect,
        }
        if text_rect is not None:
            best_candidate = candidate
            break
        if best_candidate is None:
            best_candidate = candidate

    if best_candidate is None:
        return None

    page = doc[best_candidate["page_num"]]
    _render_rect(page, best_candidate["rect"], output_path)
    return public_path if output_path.exists() else None


def main():
    target_brand = str(sys.argv[1]).strip().lower() if len(sys.argv) > 1 else ""
    if target_brand and target_brand not in {"aquant", "kohler"}:
        raise SystemExit("Usage: python tools/extract_missing_catalog_images.py [aquant|kohler]")

    data = json.loads(INDEX_PATH.read_text(encoding="utf-8-sig"))
    items = data.get("stored_items", [])

    docs = {}
    updated = 0
    still_missing = []

    for item in items:
        brand = _item_brand(item)
        if brand not in {"aquant", "kohler"}:
            continue
        if target_brand and brand != target_brand:
            continue
        if item.get("images"):
            continue

        pdf_path = _pdf_for_brand(brand)
        if pdf_path is None or not pdf_path.exists():
            still_missing.append((brand, str(item.get("search_code") or item.get("name"))))
            continue

        if brand not in docs:
            docs[brand] = fitz.open(str(pdf_path))

        public_path = _extract_for_item(docs[brand], item, brand)
        if public_path:
            item["images"] = [public_path]
            updated += 1
            print(f"EXTRACTED {brand}: {item.get('search_code')} -> {public_path}")
        else:
            still_missing.append((brand, str(item.get("search_code") or item.get("name"))))

    for doc in docs.values():
        doc.close()

    INDEX_PATH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    image_root = ROOT / "static" / "images"
    cache = {}
    for current_root, _, files in os.walk(image_root):
        for filename in files:
            stem = Path(filename).stem
            compact = search_engine._compact_alnum(stem)
            if not compact:
                continue
            rel_dir = Path(current_root).relative_to(image_root).as_posix()
            rel_path = filename if rel_dir == "." else f"{rel_dir}/{filename}"
            cache.setdefault(compact, []).append(f"/static/images/{rel_path}")
    (ROOT / "image_path_cache.json").write_text(
        json.dumps({"__schema__": search_engine.CACHE_SCHEMA_VERSION, "paths": cache}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    print("")
    print(f"Extracted images: {updated}")
    print(f"Still missing: {len(still_missing)}")
    for brand, code in still_missing[:50]:
        print(f"STILL MISSING {brand}: {code}")


if __name__ == "__main__":
    main()
