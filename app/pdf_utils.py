import os
import io
import qrcode

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import arabic_reshaper
from bidi.algorithm import get_display

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(BASE_DIR, "app", "static", "fonts")
FONT_REGULAR = os.path.join(FONT_DIR, "NotoNaskhArabic-Regular.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "NotoNaskhArabic-Bold.ttf")

_FONT_REGISTERED = False


def _ensure_fonts():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    if os.path.exists(FONT_REGULAR):
        pdfmetrics.registerFont(TTFont("Arabic", FONT_REGULAR))
    if os.path.exists(FONT_BOLD):
        pdfmetrics.registerFont(TTFont("Arabic-Bold", FONT_BOLD))
    _FONT_REGISTERED = True


def ar(text):
    """إعادة تشكيل النص العربي وضبط اتجاهه للعرض الصحيح في PDF"""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)


def generate_qr_image(data, save_path):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a2b4c", back_color="white")
    img.save(save_path)
    return save_path


def generate_issued_pdf(document, save_path, verify_url):
    """
    توليد ملف PDF (صفحة الإصدار/الغلاف) يحتوي على:
    الرقم التسلسلي + QR + بيانات المرسل/المرسل إليه (FR-2.4)
    """
    _ensure_fonts()
    has_arabic_font = os.path.exists(FONT_REGULAR)
    font_name = "Arabic" if has_arabic_font else "Helvetica"
    font_bold = "Arabic-Bold" if os.path.exists(FONT_BOLD) else "Helvetica-Bold"

    # توليد QR في ملف مؤقت داخل الذاكرة
    qr_buffer = io.BytesIO()
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a2b4c", back_color="white")
    img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    from reportlab.lib.utils import ImageReader
    qr_img = ImageReader(qr_buffer)

    c = canvas.Canvas(save_path, pagesize=A4)
    width, height = A4

    primary = HexColor("#1a2b4c")
    accent = HexColor("#c9a227")
    gray = HexColor("#666666")

    def rtext(x_right, y, text, size=11, font=None, color=HexColor("#111111")):
        """كتابة نص عربي محاذى لليمين عند نقطة x_right"""
        c.setFont(font or font_name, size)
        c.setFillColor(color)
        c.drawRightString(x_right, y, ar(text))

    # ===== الترويسة =====
    c.setFillColor(primary)
    c.rect(0, height - 30 * mm, width, 30 * mm, fill=True, stroke=False)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont(font_bold, 18)
    c.drawCentredString(width / 2, height - 14 * mm, ar("منظومة تتبع المستندات الداخلية"))
    c.setFont(font_name, 11)
    c.drawCentredString(width / 2, height - 22 * mm, ar("صفحة إصدار وأرشفة مستند رسمي"))

    c.setFillColor(accent)
    c.rect(0, height - 31.5 * mm, width, 1.5 * mm, fill=True, stroke=False)

    y = height - 45 * mm
    right_margin = width - 20 * mm

    # ===== رقم المستند (بارز) =====
    c.setFillColor(primary)
    c.roundRect(20 * mm, y - 12 * mm, width - 40 * mm, 16 * mm, 3 * mm, fill=False, stroke=True)
    c.setFont(font_bold, 16)
    c.setFillColor(primary)
    c.drawCentredString(width / 2, y - 6 * mm, f"{document.number}")
    c.setFont(font_name, 9)
    c.setFillColor(gray)
    c.drawCentredString(width / 2, y - 10.5 * mm, ar("الرقم المرجعي / التسلسلي"))

    y -= 24 * mm

    # ===== جدول بيانات المستند =====
    rows = [
        ("العنوان", document.title),
        ("النوع", document.type_label()),
        ("التصنيف", document.category or "—"),
        ("القسم", document.department.name if document.department else "—"),
        ("المُرسِل", document.sender_name),
        ("المُرسَل إليه", f"{document.recipient_name} ({document.recipient_type_label()})"),
        ("الحالة", "مؤرشف"),
        ("تاريخ الإصدار", document.created_at.strftime("%Y-%m-%d %H:%M")),
    ]

    row_h = 9 * mm
    c.setLineWidth(0.4)
    for i, (label, value) in enumerate(rows):
        row_y = y - i * row_h
        if i % 2 == 0:
            c.setFillColor(HexColor("#f4f6fb"))
            c.rect(20 * mm, row_y - row_h + 2 * mm, width - 40 * mm, row_h, fill=True, stroke=False)
        rtext(right_margin, row_y - 5.5 * mm, label, size=10, font=font_bold, color=primary)
        rtext(right_margin - 45 * mm, row_y - 5.5 * mm, str(value), size=10, font=font_name, color=HexColor("#222222"))

    y = y - len(rows) * row_h - 15 * mm

    # ===== QR Code =====
    qr_size = 40 * mm
    qr_x = width / 2 - qr_size / 2
    c.drawImage(qr_img, qr_x, y - qr_size, width=qr_size, height=qr_size, mask="auto")

    c.setFont(font_name, 9)
    c.setFillColor(gray)
    c.drawCentredString(width / 2, y - qr_size - 6 * mm, ar("امسح الرمز للتحقق من صحة المستند والاطلاع عليه"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, y - qr_size - 10 * mm, verify_url)

    # ===== تذييل =====
    c.setFillColor(gray)
    c.setFont(font_name, 8)
    c.drawCentredString(width / 2, 12 * mm, ar("مستند مُولَّد آليًا من منظومة تتبع المستندات الداخلية — لا حاجة لتوقيع يدوي على هذه الصفحة"))

    c.showPage()
    c.save()
    return save_path
