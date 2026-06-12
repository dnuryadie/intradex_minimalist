"""
pi_generator.py — Proforma Invoice PDF Generator for InTradeX-Mate
Menggunakan reportlab (Platypus) untuk layout profesional.
"""

import io
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)

# ── COLOUR PALETTE ────────────────────────────────────────────────────────────
DARK_GREEN   = colors.HexColor("#1B4332")
MID_GREEN    = colors.HexColor("#2D6A4F")
LIGHT_GREEN  = colors.HexColor("#D8F3DC")
ACCENT_GOLD  = colors.HexColor("#B7950B")
TEXT_DARK    = colors.HexColor("#1A1A1A")
TEXT_GRAY    = colors.HexColor("#555555")
TABLE_HEADER = colors.HexColor("#2D6A4F")
TABLE_ALT    = colors.HexColor("#F0FAF4")
BORDER_COLOR = colors.HexColor("#AAAAAA")
WHITE        = colors.white

# ── CONFIRMATION MESSAGES (multilingual) ─────────────────────────────────────
CONFIRM_MESSAGES = {
    "English":          "Are all fields complete and ready to print?",
    "Deutsch":          "Sind alle Felder vollständig ausgefüllt und druckbereit?",
    "Nederlands":       "Zijn alle velden volledig ingevuld en klaar om af te drukken?",
    "日本語":            "すべての項目が入力済みで、印刷の準備はできていますか？",
    "한국어":            "모든 항목이 완성되었으며 인쇄 준비가 되셨습니까?",
    "العربية":           "هل جميع الحقول مكتملة وجاهزة للطباعة؟",
    "Bahasa Indonesia": "Apakah semuanya sudah diisi lengkap dan Anda ingin mencetaknya?"
}

# ── STYLES ────────────────────────────────────────────────────────────────────
def build_styles():
    base = getSampleStyleSheet()

    styles = {
        "doc_title": ParagraphStyle(
            "doc_title",
            fontSize=16, fontName="Helvetica-Bold",
            textColor=WHITE, alignment=TA_CENTER,
            spaceAfter=0, leading=20
        ),
        "doc_subtitle": ParagraphStyle(
            "doc_subtitle",
            fontSize=9, fontName="Helvetica",
            textColor=colors.HexColor("#C8E6C9"), alignment=TA_CENTER,
            spaceAfter=0
        ),
        "section_header": ParagraphStyle(
            "section_header",
            fontSize=8, fontName="Helvetica-Bold",
            textColor=WHITE, alignment=TA_LEFT,
            leftIndent=4, spaceAfter=0, spaceBefore=0
        ),
        "label": ParagraphStyle(
            "label",
            fontSize=8, fontName="Helvetica-Bold",
            textColor=TEXT_GRAY, spaceAfter=1
        ),
        "value": ParagraphStyle(
            "value",
            fontSize=9, fontName="Helvetica",
            textColor=TEXT_DARK, spaceAfter=2
        ),
        "placeholder": ParagraphStyle(
            "placeholder",
            fontSize=8, fontName="Helvetica-Oblique",
            textColor=colors.HexColor("#AAAAAA"), spaceAfter=2
        ),
        "small": ParagraphStyle(
            "small",
            fontSize=7, fontName="Helvetica",
            textColor=TEXT_GRAY, spaceAfter=1
        ),
        "footer": ParagraphStyle(
            "footer",
            fontSize=7, fontName="Helvetica",
            textColor=TEXT_GRAY, alignment=TA_CENTER
        ),
        "amount": ParagraphStyle(
            "amount",
            fontSize=12, fontName="Helvetica-Bold",
            textColor=DARK_GREEN, alignment=TA_RIGHT,
            spaceAfter=0
        ),
        "normal": base["Normal"],
    }
    return styles


def val(text, styles):
    return Paragraph(str(text), styles["value"])

def lbl(text, styles):
    return Paragraph(str(text), styles["label"])

def ph(text, styles):
    return Paragraph(str(text), styles["placeholder"])


# ── SECTION HEADER BAR ────────────────────────────────────────────────────────
def section_bar(title, styles, width):
    tbl = Table(
        [[Paragraph(title, styles["section_header"])]],
        colWidths=[width]
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), MID_GREEN),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    return tbl


# ── MAIN GENERATOR ────────────────────────────────────────────────────────────
def generate_pi_pdf(
    pi_number, issue_date_str, validity_days,
    seller_name, seller_address, seller_country,
    seller_email, seller_phone,
    buyer_name, buyer_address, buyer_country,
    buyer_email, buyer_phone,
    fob_data, packaging_type,
    payment_terms, bank_details,
    notes, lang
):
    buffer = io.BytesIO()

    PAGE_W, PAGE_H = A4
    L_MARGIN = R_MARGIN = 18 * mm
    T_MARGIN = B_MARGIN = 18 * mm
    CONTENT_W = PAGE_W - L_MARGIN - R_MARGIN

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=L_MARGIN, rightMargin=R_MARGIN,
        topMargin=T_MARGIN, bottomMargin=B_MARGIN,
        title=f"Proforma Invoice {pi_number}",
        author=seller_name,
        subject="Proforma Invoice — InTradeX-Mate"
    )

    styles = build_styles()
    story  = []

    # ── VALIDITY DATE ──────────────────────────────────────────────────────────
    try:
        issue_dt      = datetime.strptime(issue_date_str, "%d %B %Y")
        validity_dt   = issue_dt + timedelta(days=int(validity_days))
        validity_str  = validity_dt.strftime("%d %B %Y")
    except Exception:
        validity_str  = f"+{validity_days} days from issue"

    # ══════════════════════════════════════════════════════════════════════════
    # HEADER BANNER
    # ══════════════════════════════════════════════════════════════════════════
    header_data = [[
        Paragraph("PROFORMA INVOICE", styles["doc_title"]),
    ]]
    header_tbl = Table(header_data, colWidths=[CONTENT_W])
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), DARK_GREEN),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(header_tbl)

    sub_data = [[Paragraph(
        "InTradeX-Mate &nbsp;|&nbsp; A Strategic Initiative from MAGASTU &nbsp;|&nbsp; Indonesian Spice Export",
        styles["doc_subtitle"]
    )]]
    sub_tbl = Table(sub_data, colWidths=[CONTENT_W])
    sub_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), MID_GREEN),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(sub_tbl)
    story.append(Spacer(1, 6))

    # ══════════════════════════════════════════════════════════════════════════
    # LOGO PLACEHOLDER + PI META (side by side)
    # ══════════════════════════════════════════════════════════════════════════
    logo_cell = Table(
        [[Paragraph(
            "<b>[  SELLER COMPANY LOGO  ]</b><br/>"
            "<font size='6' color='#AAAAAA'>"
            "Replace with official logo (PNG transparent, min 300dpi)"
            "</font>",
            ParagraphStyle("lph", fontSize=8, fontName="Helvetica-Bold",
                           textColor=colors.HexColor("#BBBBBB"), alignment=TA_CENTER)
        )]],
        colWidths=[70 * mm], rowHeights=[16 * mm]   # dikecilkan dari 28mm → 16mm
    )
    logo_cell.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F7F7F7")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))

    meta_right = [
        [lbl("PI Number", styles),  val(pi_number, styles)],
        [lbl("Issue Date", styles), val(issue_date_str, styles)],
        [lbl("Valid Until", styles),val(f"{validity_str}  ({validity_days} days)", styles)],
    ]
    meta_tbl = Table(meta_right, colWidths=[28 * mm, 62 * mm])
    meta_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    top_row = Table([[logo_cell, meta_tbl]], colWidths=[72 * mm, 95 * mm])
    top_row.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (1, 0), (1, 0), 12),
    ]))
    story.append(top_row)
    story.append(Spacer(1, 4))

    # ══════════════════════════════════════════════════════════════════════════
    # SELLER / BUYER (2 columns)
    # ══════════════════════════════════════════════════════════════════════════
    COL_W = (CONTENT_W - 6) / 2

    def party_block(title, name, address, country, email, phone, styles, width):
        block = [
            section_bar(title, styles, width),
            Spacer(1, 4),
        ]
        if name:
            block += [lbl("Company Name", styles), val(name, styles)]
        else:
            block += [lbl("Company Name", styles),
                      ph("[ Enter company name ]", styles)]

        if address:
            block += [lbl("Address", styles), val(address, styles)]
        else:
            block += [lbl("Address", styles),
                      ph("[ Enter full address ]", styles)]

        block += [lbl("Country", styles), val(country or "[ Enter country ]", styles)]

        if email:
            block += [lbl("Email", styles), val(email, styles)]
        else:
            block += [lbl("Email", styles),
                      ph("[ Enter email address ]", styles)]

        if phone:
            block += [lbl("Phone / WhatsApp", styles), val(phone, styles)]
        else:
            block += [lbl("Phone / WhatsApp", styles),
                      ph("[ Enter phone number ]", styles)]

        return block

    seller_col = party_block(
        "SELLER", seller_name, seller_address, seller_country,
        seller_email, seller_phone, styles, COL_W
    )
    buyer_col = party_block(
        "BUYER / CONSIGNEE", buyer_name, buyer_address, buyer_country,
        buyer_email, buyer_phone, styles, COL_W
    )

    party_tbl = Table(
        [[seller_col, buyer_col]],
        colWidths=[COL_W, COL_W],
        hAlign="LEFT"
    )
    party_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (1, 0), (1, 0), 8),
        ("LINEAFTER",     (0, 0), (0, -1), 0.5, BORDER_COLOR),
    ]))
    story.append(KeepTogether(party_tbl))
    story.append(Spacer(1, 6))

    # ══════════════════════════════════════════════════════════════════════════
    # COMMODITY & SHIPMENT DETAILS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(section_bar("COMMODITY & SHIPMENT DETAILS", styles, CONTENT_W))
    story.append(Spacer(1, 4))

    commodity_data = [
        ["Commodity",    fob_data["commodity"],
         "HS Code",      fob_data["hs_code"]],
        ["Origin",       fob_data["origin"],
         "Loading Port", fob_data["loading_port"]],
        ["Packaging",    packaging_type,
         "Total Units",  f"{fob_data['total_units_needed']} unit(s)"],
        ["Net Weight",   f"{fob_data['net_weight_kg']:,} Kg",
         "Gross Weight", f"{fob_data['gross_weight_kg']:,} Kg"],
    ]

    CW = CONTENT_W / 4
    comm_tbl = Table(
        [[lbl(r[0], styles), val(r[1], styles),
          lbl(r[2], styles), val(r[3], styles)]
         for r in commodity_data],
        colWidths=[CW * 0.7, CW * 1.3, CW * 0.7, CW * 1.3]
    )
    comm_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [WHITE, TABLE_ALT]),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.25, BORDER_COLOR),
    ]))
    story.append(comm_tbl)
    story.append(Spacer(1, 6))

    # ══════════════════════════════════════════════════════════════════════════
    # PRICING TABLE
    # ══════════════════════════════════════════════════════════════════════════
    story.append(section_bar(
        f"PRICING  (Incoterm: FOB {fob_data['loading_port']}, Indonesia)",
        styles, CONTENT_W
    ))
    story.append(Spacer(1, 3))

    price_header = [
        Paragraph("Description", styles["section_header"]),
        Paragraph("HS Code",     styles["section_header"]),
        Paragraph("Qty (Kg)",    styles["section_header"]),
        Paragraph("Unit Price (USD/Kg)", styles["section_header"]),
        Paragraph("Total (USD)", styles["section_header"]),
    ]
    price_row = [
        val(fob_data["commodity"], styles),
        val(fob_data["hs_code"],   styles),
        val(f"{fob_data['net_weight_kg']:,}", styles),
        val(f"${fob_data['fob_price_per_kg']:.4f}", styles),
        val(f"${fob_data['fob_total_usd']:,.2f}", styles),
    ]
    total_row = [
        Paragraph("<b>TOTAL FOB VALUE</b>",
                  ParagraphStyle("tb", fontSize=9, fontName="Helvetica-Bold",
                                 textColor=DARK_GREEN)),
        "", "", "",
        Paragraph(f"<b>USD {fob_data['fob_total_usd']:,.2f}</b>",
                  ParagraphStyle("tv", fontSize=10, fontName="Helvetica-Bold",
                                 textColor=DARK_GREEN, alignment=TA_RIGHT)),
    ]

    price_tbl = Table(
        [price_header, price_row, total_row],
        colWidths=[CONTENT_W * 0.35, CONTENT_W * 0.12,
                   CONTENT_W * 0.13, CONTENT_W * 0.20, CONTENT_W * 0.20]
    )
    price_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), TABLE_HEADER),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("BACKGROUND",    (0, 2), (-1, 2), LIGHT_GREEN),
        ("LINEBELOW",     (0, 0), (-1, 0), 1, DARK_GREEN),
        ("LINEABOVE",     (0, 2), (-1, 2), 1, MID_GREEN),
        ("LINEBELOW",     (0, 1), (-1, 1), 0.25, BORDER_COLOR),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (2, 0), (-1, -1), "RIGHT"),
        ("SPAN",          (0, 2), (3, 2)),
    ]))
    story.append(price_tbl)
    story.append(Spacer(1, 6))

    # ══════════════════════════════════════════════════════════════════════════
    # PAYMENT TERMS + BANK DETAILS (2 columns)
    # ══════════════════════════════════════════════════════════════════════════
    pay_col = [
        section_bar("PAYMENT TERMS", styles, COL_W),
        Spacer(1, 3),
        val(payment_terms, styles),
    ]

    bank_col = [
        section_bar("BANK DETAILS", styles, COL_W),
        Spacer(1, 3),
    ]
    if bank_details and bank_details.strip():
        bank_col.append(val(bank_details, styles))
    else:
        bank_col += [
            ph("[ Bank Name ]", styles),
            ph("[ Account Name ]", styles),
            ph("[ Account Number ]", styles),
            ph("[ Swift / BIC Code ]", styles),
            ph("[ Bank Address ]", styles),
        ]

    pay_tbl = Table(
        [[pay_col, bank_col]],
        colWidths=[COL_W, COL_W]
    )
    pay_tbl.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
        ("LINEAFTER",   (0, 0), (0, -1), 0.5, BORDER_COLOR),
    ]))
    story.append(KeepTogether(pay_tbl))
    story.append(Spacer(1, 6))

    # ══════════════════════════════════════════════════════════════════════════
    # NOTES + SIGNATURE (side by side untuk hemat ruang vertikal)
    # ══════════════════════════════════════════════════════════════════════════
    default_notes = (
        f"1. PI valid for {validity_days} calendar days from issue date.\n"
        f"2. Prices subject to change after validity period.\n"
        f"3. Commercial Invoice issued upon order confirmation.\n"
        f"4. Phytosanitary Cert, COO, COA available upon request.\n"
        f"5. Force majeure clauses apply per international trade practice."
    )
    note_text = notes if (notes and notes.strip()) else default_notes

    notes_col = [section_bar("NOTES & CONDITIONS", styles, COL_W), Spacer(1, 3)]
    for line in note_text.split("\n"):
        if line.strip():
            notes_col.append(Paragraph(line.strip(), styles["small"]))

    sig_col_w = COL_W

    def sig_block(title, name):
        return [
            Paragraph(f"<b>{title}</b>",
                      ParagraphStyle("st", fontSize=8, fontName="Helvetica-Bold", textColor=TEXT_GRAY)),
            Spacer(1, 18),
            HRFlowable(width=sig_col_w * 0.85, thickness=0.5, color=BORDER_COLOR),
            Spacer(1, 2),
            ph("[ Authorised Signature & Company Stamp ]", styles),
            lbl("Name", styles),
            val(name if name else "[ Name & Title ]", styles),
            lbl("Date", styles),
            ph("[ dd / mm / yyyy ]", styles),
        ]

    sig_col = [
        section_bar("AUTHORISATION & ACCEPTANCE", styles, sig_col_w),
        Spacer(1, 3),
        Table(
            [[sig_block("SELLER", seller_name), sig_block("BUYER / CONSIGNEE", buyer_name)]],
            colWidths=[sig_col_w / 2 - 2, sig_col_w / 2 - 2]
        )
    ]

    bottom_tbl = Table([[notes_col, sig_col]], colWidths=[COL_W, COL_W])
    bottom_tbl.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
        ("LINEAFTER",   (0, 0), (0, -1), 0.5, BORDER_COLOR),
    ]))
    story.append(bottom_tbl)
    story.append(Spacer(1, 4))

    # ══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════════════════
    story.append(HRFlowable(width=CONTENT_W, thickness=0.5, color=MID_GREEN))
    story.append(Paragraph(
        f"Generated by InTradeX-Mate &nbsp;|&nbsp; {pi_number} &nbsp;|&nbsp; "
        f"Issued: {issue_date_str} &nbsp;|&nbsp; "
        f"This document is computer-generated and valid without a physical stamp unless otherwise stated.",
        styles["footer"]
    ))

    # ── BUILD ─────────────────────────────────────────────────────────────────
    doc.build(story)
    buffer.seek(0)
    return buffer