import os
import sys
import urllib.request
from datetime import datetime
from html import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image as RLImage, HRFlowable, Flowable, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

from app_paths import resolve_data_dir

# ── Company constants ──────────────────────────────────────────────────────────
COMPANY_NAME     = "Shreeji Ceramica"
COMPANY_TAGLINE  = "Redefining Luxury"
COMPANY_PHONE    = "+91 9033745455"
COMPANY_EMAIL    = "shreejiceramica303@gmail.com"
COMPANY_LOGO_URL = "https://www.shreejiceramica.com/tiles/vadodara-logo.png"

def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _safe_quantity(value, default=1.0):
    parsed = _to_float(value, default)
    return parsed if parsed > 0 else default

def _normalize_room_name(value):
    room_name = str(value or "").strip()
    return room_name.upper() if room_name else "GENERAL"

def _format_quantity(value):
    qty = _safe_quantity(value, 1.0)
    return str(int(qty)) if float(qty).is_integer() else f"{qty:g}"

def _line_total(item):
    qty = _safe_quantity(item.get("quantity"), 1.0)
    price = _to_float(item.get("price"), 0.0)
    disc = _to_float(item.get("discount"), 0.0)
    gross = qty * price
    return gross - (gross * disc / 100.0)

def _line_taxable_total(item, discount_percent=0.0):
    line_after_item_discount = _line_total(item)
    global_discount_amount = line_after_item_discount * (discount_percent / 100.0)
    return line_after_item_discount - global_discount_amount


def _resolve_case_insensitive_path(root_dir, relative_path):
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


def _find_image_by_basename(root_dir, filename):
    target_name = str(filename or "").strip().lower()
    if not target_name:
        return ""

    for current_root, _, files in os.walk(root_dir):
        for current_file in files:
            if current_file.lower() == target_name:
                return os.path.join(current_root, current_file)
    return ""


def _resolve_item_image(base_dir, item):
    img_p = str(item.get("image") or "").strip()
    
    # Check if the image is a placeholder, page-extracted, or empty
    import re
    is_placeholder_or_pe = (
        not img_p or
        "image_not_found" in img_p.lower() or
        "image not found" in img_p.lower() or
        bool(re.search(r'_p\d+_i\d+|Page', img_p, re.IGNORECASE))
    )

    if not is_placeholder_or_pe:
        is_frozen = getattr(sys, "frozen", False)
        exe_dir = os.path.dirname(os.path.abspath(sys.executable)) if is_frozen else base_dir
        data_dir = resolve_data_dir(is_frozen, exe_dir)

        candidate_paths = []
        if img_p.startswith("/static/images/"):
            rel = img_p.split("?")[0].replace("/static/images/", "", 1)  # strip cache buster ?v=...
            image_roots = [
                os.path.join(data_dir, "static", "images"),
                os.path.join(base_dir, "static", "images"),
                os.path.join(exe_dir, "static", "images"),
            ]

            for root_dir in image_roots:
                resolved = _resolve_case_insensitive_path(root_dir, rel)
                if resolved:
                    candidate_paths.append(resolved)

            if "/" not in rel.replace("\\", "/"):
                basename_match = os.path.basename(rel)
                for root_dir in image_roots:
                    recursive_match = _find_image_by_basename(root_dir, basename_match)
                    if recursive_match:
                        candidate_paths.append(recursive_match)
        elif os.path.isabs(img_p):
            candidate_paths.append(img_p)
        elif img_p.startswith("http://") or img_p.startswith("https://"):
            cache_dir = os.path.join(data_dir, "static", "images", "_quote_cache")
            os.makedirs(cache_dir, exist_ok=True)
            filename = os.path.basename(img_p.split("?", 1)[0]) or f"quote_image_{int(datetime.now().timestamp())}.jpg"
            cached_path = os.path.join(cache_dir, filename)
            if not os.path.exists(cached_path):
                try:
                    urllib.request.urlretrieve(img_p, cached_path)
                except Exception:
                    cached_path = ""
            if cached_path:
                candidate_paths.append(cached_path)

        for real_p in candidate_paths:
            if real_p and os.path.exists(real_p):
                try:
                    if os.path.getsize(real_p) > 500:
                        return RLImage(real_p, width=58, height=58, kind='bound')
                except Exception:
                    continue

    # Return a stylized "No Image" Paragraph so it is rendered explicitly in the PDF table
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    no_image_style = ParagraphStyle(
        'NoImageCell',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#64748b"), # professional slate gray
        alignment=1, # Center
    )
    return Paragraph("No Image", no_image_style)

def _build_item_description(item, styles):
    import re
    def strip_product_code(text: str) -> str:
        val = str(text or "").strip()
        if not val:
            return ""
        dash_index = val.find(" - ")
        if dash_index > 0:
            first_part = val[:dash_index].strip()
            if any(c.isdigit() for c in first_part) and len(first_part) < 25:
                val = val[dash_index + 3:].strip()
        val = re.sub(r'\s*[\(\[]\s*K-[A-Z0-9\-]+\s*[\)\]]', '', val, flags=re.IGNORECASE)
        val = re.sub(r'\s*[\(\[]\s*\d{4,}[A-Z0-9\-]*\s*[\)\]]', '', val, flags=re.IGNORECASE)
        return val.strip()

    raw = str(item.get("rawText") or item.get("name") or "Unknown Item")
    lines = [strip_product_code(line) for line in raw.split("\n")]
    parts = [segment.strip() for segment in lines if segment.strip()]
    
    name_str = strip_product_code(str(item.get("name") or (parts[0] if parts else "Unknown Item"))).strip() or "Unknown Item"
    extra_lines = parts[1:] if len(parts) > 1 else []
    
    # Avoid duplicate name rendering on the second line if it is exactly identical
    if extra_lines and extra_lines[0] == name_str:
        extra_lines = extra_lines[1:]
        
    extra_html = "<br/>".join(escape(line) for line in extra_lines)
    description_html = f"<b>{escape(name_str)}</b>"
    if extra_html:
        description_html += f"<br/>{extra_html}"

    return Paragraph(
        description_html,
        ParagraphStyle(
            'ItemDesc',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#1e293b"),
        )
    )

def _get_logo_path(base_dir):
    """Return local logo path; download from web if not already saved."""
    local = os.path.join(base_dir, "static", "shreeji_logo.png")
    if os.path.exists(local):
        return local
    try:
        os.makedirs(os.path.join(base_dir, "static"), exist_ok=True)
        urllib.request.urlretrieve(COMPANY_LOGO_URL, local)
        return local
    except Exception:
        return None

def generate_quote(data):
    """Generates a premium PDF quote matching the user's reference exactly."""
    show_bg_logo  = data.get("show_bg_logo", False)
    made_by       = str(data.get("made_by") or "").strip()
    made_by_phone = str(data.get("made_by_phone") or "").strip()
    items         = data.get("items", [])
    discount_type = data.get("discount_type", "percent")
    discount_flat = _to_float(data.get("discount_flat", 0))
    discount_percent = _to_float(data.get("discount_percent", 0))
    gst_rate      = _to_float(data.get("gst_rate", 0))
    output_path   = str(data.get("output_path") or "quotation.pdf").strip() or "quotation.pdf"
    quote_number  = data.get("quote_number", "")
    today_str     = datetime.now().strftime("%d %B %Y")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = _get_logo_path(base_dir)

    # ── Background watermark callback (Large Pictorial Logo) ─────────
    def draw_background(canvas, doc):
        page_w, page_h = A4
        if show_bg_logo and logo_path and os.path.exists(logo_path):
            canvas.saveState()
            canvas.setFillAlpha(0.12)  # Professional watermark opacity
            logo_w, logo_h = 280, 175
            canvas.drawImage(
                logo_path,
                (page_w - logo_w) / 2,
                (page_h - logo_h) / 2 - 40,
                width=logo_w,
                height=logo_h,
                preserveAspectRatio=True,
                mask='auto',
            )
            canvas.restoreState()

    # Document setup
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            rightMargin=30, leftMargin=30,
                            topMargin=20, bottomMargin=25)
    
    styles = getSampleStyleSheet()
    elements = []

    # ── 1. Header Branding section ──────────────────────────────────────────
    if show_bg_logo:
        # A. Brand Logos (Aquant, Kohler)
        def _brand_img(b_name, filename, w=70, h=35):
            p = os.path.join(base_dir, "static", filename)
            # Fallback if specific brand files missing/broken
            if b_name == 'AQUANT' and (not os.path.exists(p) or os.path.getsize(p) < 100):
                 p = os.path.join(base_dir, "static", "gen_aquant.png")
            if b_name == 'KOHLER' and (not os.path.exists(p) or os.path.getsize(p) < 100):
                 p = os.path.join(base_dir, "static", "gen_kohler.png")
            
            if os.path.exists(p) and os.path.getsize(p) > 500:
                try: return RLImage(p, width=w, height=h, kind='proportional')
                except: pass
            
            brand_style = ParagraphStyle('bs', parent=styles['Normal'], fontSize=7, alignment=1)
            return Table([[Paragraph(f"<b>{b_name}</b>", brand_style)]], colWidths=[w])

        aquant_img  = _brand_img('AQUANT', "brand_aquant.png")
        kohler_img  = _brand_img('KOHLER', "brand_kohler.png")
        
        brands_row = Table([[kohler_img, aquant_img]], colWidths=[80, 80])
        brands_row.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))

        # B. Center: empty spacer
        info_cell = [Spacer(1, 4)]

        # C. Shreeji Logo (Far Right, without phone number)
        shreeji_logo = ""
        if logo_path and os.path.exists(logo_path):
            shreeji_logo = RLImage(logo_path, width=145, height=105, kind='proportional')

        right_cell = [Spacer(1, 6), shreeji_logo] if shreeji_logo else []

        # Assemble Header Table
        header_table = Table([[brands_row, info_cell, right_cell]], colWidths=[170, 120, 220])
        header_table.setStyle(TableStyle([
            ('VALIGN',     (0, 0), (1, 0), 'MIDDLE'),
            ('VALIGN',     (2, 0), (2, 0), 'MIDDLE'),
            ('ALIGN',      (2, 0), (2, 0), 'CENTER'),
            ('LINEAFTER',  (0, 0), (0,  0),   0.5, colors.lightgrey),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING',(0,0), (-1,-1), 0),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 4))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#be1e2d"), spaceAfter=10))
    else:
        elements.append(Spacer(1, 40))

    if show_bg_logo:
        # ── Address Banner (above Business Proposal title, containing Address and Prepared By) ──────────────
        addr_style = ParagraphStyle('Addr', parent=styles['Normal'],
            fontSize=9, fontName='Helvetica-Bold',
            textColor=colors.white, alignment=1, leading=13)
        
        addr_text = "Opp. Indrapuri Atithi Gruh, Waghodia Road, Vadodara - 390019   |   Ph: +91 8735044244"

        addr_table = Table(
            [[Paragraph(addr_text, addr_style)]],
            colWidths=[515]
        )
        addr_table.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,-1), colors.HexColor("#1e3a5f")),
            ('TOPPADDING',   (0,0), (-1,-1), 6),
            ('BOTTOMPADDING',(0,0), (-1,-1), 6),
            ('LEFTPADDING',  (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(addr_table)
        elements.append(Spacer(1, 8))

        title_style = ParagraphStyle('TS', parent=styles['Normal'], fontSize=15, fontName='Helvetica-Bold', textColor=colors.HexColor("#e0a020"), alignment=0)
        
        meta_style = ParagraphStyle('MS', parent=styles['Normal'], fontSize=8.5, fontName='Helvetica-Bold', alignment=2, leading=11)
        quote_id = quote_number if quote_number else f"SC-{today_str.replace(' ', '')}"
        meta_text = [f"<b>No:</b> {quote_id}", f"<b>Date:</b> {today_str}"]
        if made_by:
            meta_text.append(f"<b>Prepared By: {made_by} - {made_by_phone}</b>" if made_by_phone else f"<b>Prepared By: {made_by}</b>")
        
        meta_para = Paragraph("<br/>".join(meta_text), meta_style)
        
        title_table = Table([[Paragraph("<b>BUSINESS PROPOSAL</b>", title_style), meta_para]], colWidths=[330, 185])
        title_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
        
        elements.append(title_table)
        elements.append(Spacer(1, 10))
    else:
        # Simple title when branding is off
        title_style = ParagraphStyle('TS_Plain', parent=styles['Normal'], fontSize=18, fontName='Helvetica-Bold', textColor=colors.black, alignment=1)
        elements.append(Paragraph("QUOTATION", title_style))
        elements.append(Spacer(1, 15))

    # ── 3. Bill To section ────────────────────────────────────────────────
    label_s = ParagraphStyle('L', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor("#334155"), leading=13)
    val_s = ParagraphStyle('V', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor("#64748b"), leading=13)
    
    client_data = [
        [Paragraph("Client Name:", label_s), Paragraph(data.get('client_name', 'Customer Name'), val_s)],
        [Paragraph("Mobile No:", label_s),   Paragraph(data.get('mobile', '-'), val_s)],
        [Paragraph("Company:", label_s),      Paragraph(data.get('company', '-'), val_s)],
        [Paragraph("Address:", label_s),      Paragraph(data.get('address', '-'), val_s)],
    ]
    bill_table = Table(client_data, colWidths=[85, 400])
    bill_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 0)]))
    elements.append(bill_table)
    elements.append(Spacer(1, 25))

    # ── 4. Items Table section ─────────────────────────────────────────────
    # Reverting to EXACT image format: S.No, Image, Item Description, Qty, Price, Disc(%), Amount
    room_sections = []
    room_lookup = {}
    for item in items:
        room_name = _normalize_room_name(item.get("room"))
        if room_name not in room_lookup:
            room_lookup[room_name] = {
                "name": room_name,
                "items": [],
                "display_total": 0.0,
                "taxable_total": 0.0,
            }
            room_sections.append(room_lookup[room_name])

        room_lookup[room_name]["items"].append(item)
        room_lookup[room_name]["display_total"] += _line_total(item)
        room_lookup[room_name]["taxable_total"] += _line_taxable_total(item, discount_percent)

    show_room_sections = any(str(item.get("room") or "").strip() for item in items)
    subtotal = _to_float(data.get("subtotal", 0))
    gst_amt  = _to_float(data.get("gst_amount", 0))
    grand    = _to_float(data.get("grand_total", 0))

    if show_room_sections:
        section_heading_style = ParagraphStyle(
            'RoomHeading',
            parent=styles['Normal'],
            fontSize=11.5,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor("#1f3d67"),
            spaceAfter=6,
        )
        section_cell_style = ParagraphStyle(
            'RoomCell',
            parent=styles['Normal'],
            fontSize=7.6,
            leading=9,
            textColor=colors.HexColor("#334155"),
            alignment=1,
        )

        for section in room_sections:
            elements.append(Paragraph(section["name"], section_heading_style))

            show_disc_col = not (discount_percent > 0 or discount_flat > 0)
            if show_disc_col:
                section_rows = [[
                    "#",
                    "IMG",
                    "Item Details",
                    "SKU",
                    "Size",
                    "Qty",
                    "Rate",
                    "Disc %",
                    "Amount",
                ]]
                col_widths = [20, 62, 158, 48, 50, 30, 58, 39, 67]
            else:
                section_rows = [[
                    "#",
                    "IMG",
                    "Item Details",
                    "SKU",
                    "Size",
                    "Qty",
                    "Rate",
                    "Amount",
                ]]
                col_widths = [20, 62, 197, 48, 50, 30, 58, 67]

            for item_index, item in enumerate(section["items"], start=1):
                qty = _safe_quantity(item.get("quantity"), 1.0)
                price = _to_float(item.get("price"), 0.0)
                disc = _to_float(item.get("discount"), 0.0)
                amount = _line_total(item)

                row_cells = [
                    str(item_index),
                    _resolve_item_image(base_dir, item),
                    _build_item_description(item, styles),
                    Paragraph(escape(str(item.get("sku") or "-")), section_cell_style),
                    Paragraph(escape(str(item.get("size") or "-")), section_cell_style),
                    Paragraph(escape(_format_quantity(qty)), section_cell_style),
                    Paragraph(escape(f"Rs. {price:,.2f}"), section_cell_style),
                ]
                if show_disc_col:
                    row_cells.append(Paragraph(escape(f"{disc:g}%"), section_cell_style))
                row_cells.append(
                    Paragraph(
                        escape(f"Rs. {amount:,.2f}"),
                        ParagraphStyle('AmountCell', parent=section_cell_style, fontName='Helvetica-Bold', alignment=2)
                    )
                )
                section_rows.append(row_cells)

            # Calculate rate total (sum of all item prices × qty, before discount)
            rate_total = sum(
                _to_float(it.get("price"), 0.0) * _safe_quantity(it.get("quantity"), 1.0)
                for it in section["items"]
            )

            total_cells = [Paragraph("<b>TOTAL</b>", section_cell_style)]
            num_cols = len(section_rows[0])
            # Fill blanks up to (but not including) Rate and Amount columns
            for _ in range(num_cols - 3):
                total_cells.append("")
            # Rate total cell
            total_cells.append(
                Paragraph(
                    f"<b>Rs. {rate_total:,.2f}</b>",
                    ParagraphStyle('RateTotal', parent=section_cell_style, fontName='Helvetica-Bold', alignment=2)
                )
            )
            # Skip disc % column if present (it's already counted in num_cols - 3)
            if show_disc_col:
                total_cells.append("")  # empty disc % cell
            # Amount total cell
            total_cells.append(
                Paragraph(
                    f"<b>Rs. {section['display_total']:,.2f}</b>",
                    ParagraphStyle('SectionTotal', parent=section_cell_style, fontName='Helvetica-Bold', alignment=2)
                )
            )
            section_rows.append(total_cells)

            section_table = Table(
                section_rows,
                colWidths=col_widths,
                repeatRows=1,
            )

            last_row_index = len(section_rows) - 1
            section_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (2, 1), (4, last_row_index - 1), 'LEFT'),
                ('ALIGN', (5, 1), (6 if not show_disc_col else 7, last_row_index - 1), 'CENTER'),
                ('ALIGN', (-1, 1), (-1, last_row_index), 'RIGHT'),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#d7dee8")),
                ('INNERGRID', (0, 0), (-1, -1), 0.35, colors.HexColor("#d7dee8")),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('SPAN', (0, last_row_index), (-2, last_row_index)),
                ('BACKGROUND', (0, last_row_index), (-1, last_row_index), colors.white),
            ]))


            elements.append(section_table)
            elements.append(Spacer(1, 12))

        overall_totals = [["Final Amount", f"Rs. {subtotal:,.2f}"]]
        if discount_percent > 0:
            discount_amount = subtotal - (grand - gst_amt)
            overall_totals.append([f"Discount ({discount_percent:g}%)", f"- Rs. {discount_amount:,.2f}"])
        if gst_rate > 0:
            overall_totals.append([f"GST ({gst_rate:g}%)", f"Rs. {gst_amt:,.2f}"])
        overall_totals.append(["Grand Total", f"Rs. {grand:,.2f}"])


        overall_totals_table = Table(overall_totals, colWidths=[140, 120], hAlign='RIGHT')
        overall_totals_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#d7dee8")),
            ('INNERGRID', (0, 0), (-1, -1), 0.35, colors.HexColor("#d7dee8")),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor("#0f2f57")),
        ]))
        elements.append(overall_totals_table)
        elements.append(Spacer(1, 18))
    else:
        show_disc_col = not (discount_percent > 0 or discount_flat > 0)
        if show_disc_col:
            header_row = ["S.No", "Image", "Item Description", "Qty", "Price", "Disc(%)", "Amount"]
            col_widths = [30, 60, 230, 45, 65, 45, 75]
        else:
            header_row = ["S.No", "Image", "Item Description", "Qty", "Price", "Amount"]
            col_widths = [30, 60, 275, 45, 65, 75]

        table_data = [header_row]
        
        for idx, item in enumerate(items):
            qty = _safe_quantity(item.get("quantity"), 1.0)
            price = _to_float(item.get("price"), 0.0)
            disc = _to_float(item.get("discount"), 0.0)
            amount = _line_total(item)
            
            row = [
                str(idx + 1),
                _resolve_item_image(base_dir, item),
                _build_item_description(item, styles),
                _format_quantity(qty),
                f"{price:,.2f}",
            ]
            if show_disc_col:
                row.append(f"{disc:g}%" if disc > 0 else "-")
            row.append(f"{amount:,.2f}")
            table_data.append(row)

        num_cols = len(header_row)
        def build_footer_row(label, val):
            frow = []
            for _ in range(num_cols - 4):
                frow.append("")
            frow.extend([label, val, "", ""])
            return frow

        table_data.append(build_footer_row("Final Amount:", f"Rs {subtotal:,.2f}"))
        if gst_rate > 0:
            table_data.append(build_footer_row(f"GST ({gst_rate:g}%):", f"+ Rs {gst_amt:,.2f}"))
        table_data.append(build_footer_row("Grand Total:", f"Rs {grand:,.2f}"))

        t = Table(table_data, colWidths=col_widths)
        t_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (2, 1), (2, -len(table_data)), 'LEFT'),
            ('ALIGN', (4, 1), (-1, -len(table_data)), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('BOX', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ])
        
        n_items = len(items)
        label_col = num_cols - 4
        val_col = num_cols - 3
        for r in range(n_items + 1, len(table_data)):
            t_style.add('SPAN', (0, r), (label_col - 1, r))
            t_style.add('SPAN', (val_col, r), (-1, r))
            t_style.add('ALIGN', (label_col, r), (label_col, r), 'RIGHT')
            t_style.add('ALIGN', (val_col, r), (val_col, r), 'RIGHT')
            t_style.add('FONTNAME', (label_col, r), (-1, r), 'Helvetica-Bold')
            t_style.add('BACKGROUND', (0, r), (-1, r), colors.white)
            
        t_style.add('TEXTCOLOR', (val_col, -1), (-1, -1), colors.HexColor("#0284c7"))
        t.setStyle(t_style)
        elements.append(t)
        elements.append(Spacer(1, 18))


    if show_bg_logo:
        # Room summary shown above Terms & Conditions in branded PDF.
        if room_sections:
            room_summary_title = ParagraphStyle(
                'RSTitle',
                parent=styles['Normal'],
                fontSize=11,
                fontName='Helvetica-Bold',
                textColor=colors.white,
                alignment=1,
            )
            room_summary_label = ParagraphStyle(
                'RSLabel',
                parent=styles['Normal'],
                fontSize=10.5,
                fontName='Helvetica',
                textColor=colors.HexColor("#1e3a5f"),
                alignment=1,
            )
            room_summary_value = ParagraphStyle(
                'RSValue',
                parent=styles['Normal'],
                fontSize=10.5,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor("#1e3a5f"),
                alignment=2,
            )
            room_summary_final_label = ParagraphStyle(
                'RSFinalLabel',
                parent=styles['Normal'],
                fontSize=11,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor("#0f2f57"),
                alignment=1,
            )
            room_summary_final_value = ParagraphStyle(
                'RSFinalValue',
                parent=styles['Normal'],
                fontSize=11,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor("#c99732"),
                alignment=2,
            )

            room_summary_data = [[Paragraph("SUMMARY OF ALL BATH ROOM", room_summary_title), ""]]
            for section in room_sections:
                room_summary_data.append([
                    Paragraph(section["name"], room_summary_label),
                    Paragraph(f"Rs. {section['taxable_total']:,.2f}", room_summary_value),
                ])

            if gst_rate > 0:
                gst_label = f"GST ({gst_rate:g}%)"
                room_summary_data.append([
                    Paragraph(gst_label, room_summary_label),
                    Paragraph(f"Rs. {gst_amt:,.2f}", room_summary_value),
                ])
            room_summary_data.append([
                Paragraph("FINAL AMOUNT", room_summary_final_label),
                Paragraph(f"Rs. {grand:,.2f}", room_summary_final_value),
            ])


            room_summary_table = Table(room_summary_data, colWidths=[410, 125])
            room_summary_table.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor("#1f3d67")),
                ('TEXTCOLOR', (0, 0), (1, 0), colors.white),
                ('ALIGN', (0, 0), (1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor("#d7dee8")),
                ('INNERGRID', (0, 1), (-1, -1), 0.35, colors.HexColor("#d7dee8")),
                ('BACKGROUND', (0, -1), (1, -1), colors.HexColor("#f4f6f9")),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(room_summary_table)
            elements.append(Spacer(1, 18))
        else:
            elements.append(Spacer(1, 10))
    else:
        elements.append(Spacer(1, 20))

    # ── 5. Footer & Signatory section ────────────────────────────────────
    if show_bg_logo:
        terms_title = ParagraphStyle('TT', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor("#1e293b"), spaceAfter=8)
        terms_text = ParagraphStyle('TX', parent=styles['Normal'], fontSize=8, leading=12, textColor=colors.HexColor("#475569"))
        
        terms = [
            Paragraph("Terms & Conditions:", terms_title),
            Paragraph("1. Quotation is valid for 15 days from the issued date.", terms_text),
            Paragraph("2. Payment terms 100% advance.", terms_text),
            Paragraph("3. Some products may have an associated image or photo. These are for reference only and should be considered illustrative.", terms_text),
            Paragraph("4. Freight charges will be extra.", terms_text),
            Paragraph("5. Tentative delivery period for concealed parts will be 3-5 working days, And for special finishes it will be 7 working days.", terms_text),
            Paragraph("6. Offer Value is inclusive of G.S.T.", terms_text),
            Paragraph("7. Goods once sold will not be taken back or exchanged.", terms_text),
            Paragraph("8. Subject to local jurisdiction only.", terms_text),
        ]
        
        # ── Professional Stamp Image ──────────────────────────────────────
        stamp_path = os.path.join(base_dir, "static", "stamp.png")
        if not os.path.exists(stamp_path):
            stamp_path = os.path.join(base_dir, "static", "stamp_seal.png")

        if os.path.exists(stamp_path):
            stamp_img = RLImage(stamp_path, width=115, height=115, kind='bound')
        else:
            stamp_img = Spacer(1, 115)

        signatory = [
            stamp_img,
        ]

        foot_table = Table([[terms, signatory]], colWidths=[300, 215])
        foot_table.setStyle(TableStyle([
            ('VALIGN',  (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (1,0), (1,0), 0),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ]))
        elements.append(foot_table)

    # ── 6. Extra Footer Images (Permanent for BOTH with & without letterhead) ────
    target_names = [
        "Mirror.jpeg",
        "Cleaner.jpeg",
        "Floor drain.jpeg",
        "Glass partition.jpeg",
        "Accessories.jpeg",
        "Steam generator & controller.jpeg"
    ]
    
    valid_items = []
    name_style = ParagraphStyle('ExtraImgName', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold', alignment=1, textColor=colors.HexColor("#334155"))
    
    for filename in target_names:
        p = os.path.join(base_dir, "static", filename)
        if os.path.exists(p):
            valid_items.append({
                "path": p,
                "name": os.path.splitext(filename)[0]
            })
            
    if valid_items:
        # Force title + all images onto a fresh page
        elements.append(PageBreak())

        # ── "Supporting Items" heading ──────────────────────────────────────
        supporting_title_style = ParagraphStyle(
            'SupportingTitle',
            parent=styles['Normal'],
            fontSize=14,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=6,
            spaceBefore=0,
            alignment=1,   # centred
        )
        heading_block = [
            Spacer(1, 40),   # space from top of page
            Paragraph("Supporting Items", supporting_title_style),
            HRFlowable(width="60%", thickness=1.5, color=colors.HexColor("#f59e0b"),
                       spaceAfter=24, hAlign='CENTER'),
        ]

        # ── 2-column grid (original layout), centred ────────────────────────
        COLS     = 2
        img_size = 180          # slightly bigger for a clean look
        col_w    = 180          # column width
        # Centre the 2-col table (total = 360) inside the 515pt text area
        side_pad = (515 - col_w * COLS) / 2   # ≈ 77.5 pt each side

        table_data = []
        for i in range(0, len(valid_items), COLS):
            row_items = valid_items[i:i + COLS]
            img_row  = []
            name_row = []

            for item in row_items:
                try:
                    img = RLImage(item["path"], width=img_size, height=img_size, kind='proportional')
                    img_row.append(img)
                    name_row.append(Paragraph(item["name"], name_style))
                except Exception:
                    img_row.append("")
                    name_row.append("")

            while len(img_row) < COLS:
                img_row.append("")
                name_row.append("")

            table_data.append(img_row)
            table_data.append(name_row)

        img_table = Table(table_data, colWidths=[col_w] * COLS,
                          hAlign='CENTER')   # centre the whole table

        t_style = [('ALIGN', (0, 0), (-1, -1), 'CENTER')]
        for row_idx in range(len(table_data)):
            if row_idx % 2 == 0:   # image rows
                t_style.append(('VALIGN',       (0, row_idx), (-1, row_idx), 'BOTTOM'))
                t_style.append(('TOPPADDING',   (0, row_idx), (-1, row_idx), 20))
                # Add horizontal gap between the 2 columns
                t_style.append(('RIGHTPADDING', (0, row_idx), (0, row_idx), 30))   # right pad col-0
                t_style.append(('LEFTPADDING',  (1, row_idx), (1, row_idx), 30))   # left  pad col-1
            else:                   # label rows
                t_style.append(('VALIGN',       (0, row_idx), (-1, row_idx), 'TOP'))
                t_style.append(('TOPPADDING',   (0, row_idx), (-1, row_idx), 8))
                t_style.append(('BOTTOMPADDING',(0, row_idx), (-1, row_idx), 10))
                t_style.append(('RIGHTPADDING', (0, row_idx), (0, row_idx), 30))
                t_style.append(('LEFTPADDING',  (1, row_idx), (1, row_idx), 30))

        img_table.setStyle(TableStyle(t_style))

        elements.extend(heading_block)
        elements.append(img_table)
        elements.append(Spacer(1, 40))   # space at the bottom of page


    # Build
    doc.build(elements, onFirstPage=draw_background, onLaterPages=draw_background)
