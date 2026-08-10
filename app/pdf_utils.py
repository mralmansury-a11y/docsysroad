import os
import io
import qrcode

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

import arabic_reshaper
from bidi.algorithm import get_display

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(BASE_DIR, "app", "static", "fonts")
FONT_REGULAR = os.path.join(FONT_DIR, "NotoNaskhArabic-Regular.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "NotoNaskhArabic-Bold.ttf")

# ===== الورق الرسمي (خلفية) =====
# صورة الترويسة/التذييل الرسمية للجهاز الوطني للتنمية - إدارة خدمات الطريق الدولي
PDF_ASSETS_DIR = os.path.join(BASE_DIR, "app", "static", "pdf_assets")
LETTERHEAD_PATH = os.path.join(PDF_ASSETS_DIR, "letterhead.jpg")

# حدود المنطقة الآمنة للمحتوى (بالملم من أعلى/أسفل الصفحة) بحيث لا يتداخل النص
# مع شعارات الترويسة أو بيانات التذييل الرسمية في الورقة
SAFE_TOP_MM = 46
SAFE_BOTTOM_MM = 24

_FONT_REGISTERED = False
_LETTERHEAD_READER = None
_LETTERHEAD_CHECKED = False


def _ensure_fonts():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    if os.path.exists(FONT_REGULAR):
        pdfmetrics.registerFont(TTFont("Arabic", FONT_REGULAR))
    if os.path.exists(FONT_BOLD):
        pdfmetrics.registerFont(TTFont("Arabic-Bold", FONT_BOLD))
    _FONT_REGISTERED = True


def _get_letterhead_reader():
    """يحمّل صورة الورق الرسمي مرة واحدة ويعيد استخدامها (كاش)"""
    global _LETTERHEAD_READER, _LETTERHEAD_CHECKED
    if _LETTERHEAD_CHECKED:
        return _LETTERHEAD_READER
    _LETTERHEAD_CHECKED = True
    if os.path.exists(LETTERHEAD_PATH):
        try:
            _LETTERHEAD_READER = ImageReader(LETTERHEAD_PATH)
        except Exception:
            _LETTERHEAD_READER = None
    return _LETTERHEAD_READER


def draw_letterhead_background(c, width, height):
    """
    يرسم صورة الورق الرسمي (ترويسة + تذييل + علامة مائية) كخلفية كاملة للصفحة.
    يُستدعى أول شيء عند رسم أي صفحة PDF في النظام حتى تخرج كل الملفات
    (صفحة الإصدار، والمستندات الأصلية المؤرشفة) بنفس هوية الجهاز الرسمية.
    """
    reader = _get_letterhead_reader()
    if reader is None:
        return
    c.drawImage(reader, 0, 0, width=width, height=height,
                preserveAspectRatio=False, mask=None)


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
    مطبوعة فوق الورق الرسمي الخاص بالجهاز (الترويسة والتذييل الرسميين)
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
    qr_img = ImageReader(qr_buffer)

    c = canvas.Canvas(save_path, pagesize=A4)
    width, height = A4

    primary = HexColor("#1a2b4c")
    gray = HexColor("#666666")

    # ===== خلفية الورق الرسمي (ترويسة + تذييل + علامة مائية) =====
    draw_letterhead_background(c, width, height)

    def rtext(x_right, y, text, size=11, font=None, color=HexColor("#111111")):
        """كتابة نص عربي محاذى لليمين عند نقطة x_right"""
        c.setFont(font or font_name, size)
        c.setFillColor(color)
        c.drawRightString(x_right, y, ar(text))

    # منطقة المحتوى الآمنة (لا تتداخل مع شعارات/بيانات الورق الرسمي)
    y = height - SAFE_TOP_MM * mm
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
    qr_size = 38 * mm
    qr_x = width / 2 - qr_size / 2
    # لا تسمح لصندوق QR بالنزول داخل منطقة التذييل الرسمي
    min_y = SAFE_BOTTOM_MM * mm + 12 * mm
    qr_y = max(y - qr_size, min_y)

    # خلفية بيضاء خلف QR لضمان وضوح المسح فوق العلامة المائية للورق الرسمي
    pad = 3 * mm
    c.setFillColor(HexColor("#ffffff"))
    c.roundRect(qr_x - pad, qr_y - pad, qr_size + 2 * pad, qr_size + 2 * pad, 2 * mm, fill=True, stroke=False)
    c.drawImage(qr_img, qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")

    c.setFont(font_name, 9)
    c.setFillColor(gray)
    c.drawCentredString(width / 2, qr_y - 6 * mm, ar("امسح الرمز للتحقق من صحة المستند والاطلاع عليه"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, qr_y - 10 * mm, verify_url)

    c.showPage()
    c.save()
    return save_path


def stamp_pdf_with_letterhead(input_path, output_path):
    """
    يطبع الورق الرسمي (كخلفية) خلف كل صفحة من ملف PDF موجود، ويحافظ على
    محتوى الملف الأصلي فوق الخلفية. يُستخدم لختم الملفات الأصلية المرفوعة
    (PDF) بهوية الجهاز الرسمية قبل أرشفتها/تنزيلها.

    ملاحظة: يعمل فقط على ملفات PDF. ملفات Word (doc/docx) لا يمكن ختمها
    مباشرة بهذه الطريقة لأنها ليست بصيغة PDF.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(input_path)
    if getattr(reader, "is_encrypted", False):
        raise ValueError("لا يمكن ختم ملف PDF محمي بكلمة سر")

    writer = PdfWriter()

    for page in reader.pages:
        page_w = float(page.mediabox.width)
        page_h = float(page.mediabox.height)

        # صفحة خلفية بنفس مقاس الصفحة الأصلية تحتوي على الورق الرسمي
        bg_buffer = io.BytesIO()
        bg_canvas = canvas.Canvas(bg_buffer, pagesize=(page_w, page_h))
        draw_letterhead_background(bg_canvas, page_w, page_h)
        bg_canvas.showPage()
        bg_canvas.save()
        bg_buffer.seek(0)

        bg_reader = PdfReader(bg_buffer)
        bg_page = bg_reader.pages[0]
        # دمج محتوى الصفحة الأصلية فوق خلفية الورق الرسمي
        bg_page.merge_page(page)
        writer.add_page(bg_page)

    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path
