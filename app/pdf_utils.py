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


def _draw_qr_reference_card(c, page_h, qr_img, document_number, font_bold):
    """
    يرسم بطاقة QR صغيرة + الرقم المرجعي أعلى يسار الصفحة (نفس التصميم
    المستخدم في كل مكان بالنظام لهذا الغرض) على كائن canvas مُمرَّر.
    """
    primary = HexColor("#1a2b4c")
    accent = HexColor("#c9a227")

    qr_size = 22 * mm
    qr_margin_left = 11 * mm
    qr_margin_top = 8 * mm
    qr_x = qr_margin_left
    qr_y = page_h - qr_margin_top - qr_size

    card_pad = 2 * mm
    c.setFillColor(HexColor("#ffffff"))
    c.setStrokeColor(primary)
    c.setLineWidth(0.7)
    c.roundRect(
        qr_x - card_pad, qr_y - card_pad,
        qr_size + 2 * card_pad, qr_size + 2 * card_pad,
        2 * mm, fill=True, stroke=True,
    )
    c.drawImage(qr_img, qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")

    if document_number:
        c.setFillColor(primary)
        c.setFont(font_bold, 8.5)
        c.drawCentredString(qr_x + qr_size / 2, qr_y - card_pad - 5 * mm, str(document_number))

    c.setStrokeColor(accent)
    c.setLineWidth(1.1)
    c.line(
        qr_x - card_pad, qr_y - card_pad - 7 * mm,
        qr_x + qr_size + card_pad, qr_y - card_pad - 7 * mm,
    )


def _make_qr_reader(verify_url):
    """يولّد صورة QR في الذاكرة ويعيدها كـ ImageReader جاهز للاستخدام مع reportlab"""
    qr_buffer = io.BytesIO()
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a2b4c", back_color="white")
    img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    return ImageReader(qr_buffer)


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
    رمز QR أنيق أعلى يمين الترويسة + رقم مرجعي مصغّر + بطاقة بيانات المستند
    بنفس تنسيق التصميم المعتمد، مطبوعة فوق الورق الرسمي الخاص بالجهاز
    (الترويسة والتذييل الرسميين)
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
    accent = HexColor("#c9a227")
    gray = HexColor("#666666")
    light_gray = HexColor("#eef1f6")
    border_gray = HexColor("#d9dee8")
    green_bg = HexColor("#e6f4ea")
    green_text = HexColor("#1e7d42")

    # ===== خلفية الورق الرسمي (ترويسة + تذييل + علامة مائية) =====
    draw_letterhead_background(c, width, height)

    def rtext(x_right, y, text, size=11, font=None, color=HexColor("#111111")):
        """كتابة نص عربي محاذى لليمين عند نقطة x_right"""
        c.setFont(font or font_name, size)
        c.setFillColor(color)
        c.drawRightString(x_right, y, ar(text))

    # ===== رمز QR أنيق داخل الفراغ العلوي الأيسر من الترويسة الرسمية =====
    # (الزاوية الفارغة أعلى يسار الصفحة، قبل شعار الجهاز وفوق الخط الفاصل)
    qr_size = 24 * mm
    qr_margin_left = 11 * mm
    qr_margin_top = 8 * mm
    qr_x = qr_margin_left
    qr_y = height - qr_margin_top - qr_size

    card_pad = 2.2 * mm
    c.setFillColor(HexColor("#ffffff"))
    c.setStrokeColor(primary)
    c.setLineWidth(0.7)
    c.roundRect(qr_x - card_pad, qr_y - card_pad, qr_size + 2 * card_pad, qr_size + 2 * card_pad,
                2.2 * mm, fill=True, stroke=True)
    c.drawImage(qr_img, qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")

    # خط ذهبي رفيع كلمسة أناقة أسفل بطاقة الـ QR (بدون أي نص تحته)
    c.setStrokeColor(accent)
    c.setLineWidth(1.1)
    c.line(qr_x - card_pad, qr_y - card_pad - 1.4 * mm,
           qr_x + qr_size + card_pad, qr_y - card_pad - 1.4 * mm)

    # منطقة المحتوى الآمنة (لا تتداخل مع شعارات/بيانات الورق الرسمي)
    y = height - SAFE_TOP_MM * mm
    card_left = 20 * mm
    card_right = width - 20 * mm

    # ===== الرقم المرجعي / التسلسلي (بطاقة مصغّرة أنيقة) =====
    badge_w = 62 * mm
    badge_h = 11 * mm
    badge_x = width / 2 - badge_w / 2
    badge_y = y - badge_h

    c.setFillColor(primary)
    c.roundRect(badge_x, badge_y, badge_w, badge_h, 2.4 * mm, fill=True, stroke=False)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont(font_bold, 11.5)
    c.drawCentredString(width / 2, badge_y + badge_h - 5.2 * mm, f"{document.number}")
    c.setFont(font_name, 6.3)
    c.drawCentredString(width / 2, badge_y + 2.4 * mm, ar("الرقم المرجعي / التسلسلي"))

    c.setStrokeColor(accent)
    c.setLineWidth(1.1)
    c.line(width / 2 - 22 * mm, badge_y - 3 * mm, width / 2 + 22 * mm, badge_y - 3 * mm)

    y = badge_y - 14 * mm

    # ===== بطاقة بيانات المستند =====
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

    header_h = 12 * mm
    row_h = 15 * mm
    card_h = header_h + row_h * len(rows)
    card_top = y
    card_bottom = card_top - card_h

    # إطار البطاقة الخارجي (خلفية بيضاء + حدود)
    c.setFillColor(HexColor("#ffffff"))
    c.setStrokeColor(border_gray)
    c.setLineWidth(0.8)
    c.roundRect(card_left, card_bottom, card_right - card_left, card_h, 3 * mm, fill=True, stroke=True)

    # رأس البطاقة (شريط كحلي)
    c.setFillColor(primary)
    c.roundRect(card_left, card_top - header_h, card_right - card_left, header_h, 3 * mm, fill=True, stroke=False)
    # تغطية الزوايا السفلية للرأس لتبقى مربّعة (فوق صفوف الجدول مباشرة)
    c.rect(card_left, card_top - header_h, card_right - card_left, header_h / 2, fill=True, stroke=False)

    c.setFillColor(HexColor("#ffffff"))
    c.setFont(font_bold, 9)
    c.drawString(card_left + 5 * mm, card_top - header_h / 2 - 1.6 * mm, "DOCUMENT DETAILS")
    c.setFont(font_bold, 12)
    c.drawRightString(card_right - 5 * mm, card_top - header_h / 2 - 1.8 * mm, ar("بيانات المستند"))

    # صفوف البيانات
    pill_w = 34 * mm
    pill_h = 9 * mm
    pill_right = card_right - 4 * mm

    for i, (label, value) in enumerate(rows):
        row_top = card_top - header_h - i * row_h
        row_mid = row_top - row_h / 2

        pill_x = pill_right - pill_w
        pill_y = row_mid - pill_h / 2

        if label == "الحالة":
            # قيمة الحالة كشارة خضراء بدل النص العادي
            status_w = 26 * mm
            status_h = 8 * mm
            status_x = pill_x - 4 * mm - status_w
            status_y = row_mid - status_h / 2
            c.setFillColor(green_bg)
            c.roundRect(status_x, status_y, status_w, status_h, 2 * mm, fill=True, stroke=False)
            c.setFillColor(green_text)
            c.setFont(font_bold, 9.5)
            c.drawCentredString(status_x + status_w / 2, row_mid - 1.6 * mm, ar(value))
        else:
            rtext(pill_x - 4 * mm, row_mid - 1.6 * mm, str(value), size=10.5,
                  font=font_name, color=HexColor("#222222"))

        c.setFillColor(light_gray)
        c.roundRect(pill_x, pill_y, pill_w, pill_h, 2 * mm, fill=True, stroke=False)
        c.setFillColor(primary)
        c.setFont(font_bold, 10)
        c.drawCentredString(pill_x + pill_w / 2, row_mid - 1.6 * mm, ar(label))

        if i < len(rows) - 1:
            c.setStrokeColor(border_gray)
            c.setLineWidth(0.4)
            c.line(card_left + 4 * mm, row_top - row_h, card_right - 4 * mm, row_top - row_h)

    y = card_bottom - 10 * mm

    # ===== بطاقة رمز التحقق (QR) أسفل الصفحة =====
    note_h = 16 * mm
    note_top = y
    note_bottom = note_top - note_h

    c.setFillColor(HexColor("#ffffff"))
    c.setStrokeColor(border_gray)
    c.setLineWidth(0.8)
    c.roundRect(card_left, note_bottom, card_right - card_left, note_h, 2.5 * mm, fill=True, stroke=True)

    # أيقونة صح صغيرة داخل مربع كحلي
    icon_size = 6 * mm
    icon_x = card_right - 8 * mm - icon_size
    icon_y = note_top - 5 * mm - icon_size
    c.setFillColor(primary)
    c.roundRect(icon_x, icon_y, icon_size, icon_size, 1.3 * mm, fill=True, stroke=False)
    c.setStrokeColor(HexColor("#ffffff"))
    c.setLineWidth(1.1)
    c.line(icon_x + 1.4 * mm, icon_y + 3 * mm, icon_x + 2.6 * mm, icon_y + 1.6 * mm)
    c.line(icon_x + 2.6 * mm, icon_y + 1.6 * mm, icon_x + icon_size - 1.2 * mm, icon_y + icon_size - 1.4 * mm)

    c.setFillColor(primary)
    c.setFont(font_bold, 10.5)
    c.drawRightString(icon_x - 3 * mm, note_top - 6.4 * mm, ar("رمز التحقق"))
    c.setFont(font_bold, 9)
    c.drawString(card_left + 5 * mm, note_top - 6.4 * mm, "QR")

    c.setFont(font_name, 8)
    c.setFillColor(gray)
    c.drawCentredString(width / 2, note_bottom + 4.5 * mm,
                         ar("متوفر أعلى الصفحة — امسحه للاطلاع على المستند والتحقق من صحته"))

    c.showPage()
    c.save()
    return save_path


def stamp_pdf_with_qr(input_path, output_path, verify_url, document_number):
    """
    يُضيف بطاقة رمز QR صغيرة + الرقم المرجعي أعلى الصفحة الأولى فقط من
    ملف PDF موجود، دون طباعة أي ورق رسمي (letterhead) ودون أي تعديل على
    بقية الصفحات - يبقى محتوى الملف كما هو تمامًا باستثناء إضافة بطاقة
    QR في الزاوية العلوية اليسرى من الصفحة الأولى.

    يُستخدم لختم الملف الأصلي المرفوع (PDF) عند الأرشفة (FR-2/FR-3)،
    بنفس فكرة stamp_docx_with_qr المستخدمة لملفات Word في
    app/docx_utils.py (ترويسة الصفحة الأولى فقط، بدون تغيير باقي الملف).

    لطباعة الورق الرسمي (letterhead) خلف الصفحات استخدم
    stamp_pdf_with_letterhead بدلاً من ذلك.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(input_path)
    if getattr(reader, "is_encrypted", False):
        raise ValueError("لا يمكن ختم ملف PDF محمي بكلمة سر")

    _ensure_fonts()
    font_bold = "Arabic-Bold" if os.path.exists(FONT_BOLD) else "Helvetica-Bold"
    qr_img = _make_qr_reader(verify_url)

    writer = PdfWriter()

    for index, page in enumerate(reader.pages):
        if index == 0:
            page_w = float(page.mediabox.width)
            page_h = float(page.mediabox.height)

            overlay_buffer = io.BytesIO()
            overlay_canvas = canvas.Canvas(overlay_buffer, pagesize=(page_w, page_h))
            _draw_qr_reference_card(overlay_canvas, page_h, qr_img, document_number, font_bold)
            overlay_canvas.showPage()
            overlay_canvas.save()
            overlay_buffer.seek(0)

            overlay_reader = PdfReader(overlay_buffer)
            overlay_page = overlay_reader.pages[0]
            # دمج بطاقة QR فوق محتوى الصفحة الأصلية (فوقه، وليس خلفه كما في حالة الورق الرسمي)
            page.merge_page(overlay_page)

        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path


def stamp_pdf_with_letterhead(input_path, output_path, verify_url=None, document_number=None):
    """
    يطبع الورق الرسمي (كخلفية) خلف كل صفحة من ملف PDF موجود، ويحافظ على
    محتوى الملف الأصلي فوق الخلفية. يُستخدم لختم الملفات الأصلية المرفوعة
    (PDF) بهوية الجهاز الرسمية قبل أرشفتها/تنزيلها.

    إذا مُرِّر verify_url (ويُفضَّل مع document_number أيضًا)، تُضاف بطاقة
    رمز QR صغيرة + الرقم المرجعي فوق الورق الرسمي في الصفحة الأولى فقط من
    الملف (لا تتكرر في بقية الصفحات) — هذه الحالة تُستخدم عند توليد نسخة
    "الملف الأصلي مع الباركود والرقم المرجعي" عند الطلب من صفحة تفاصيل
    المستند (download_original_marked). عند عدم تمرير verify_url (كما في
    ختم الملف الأصلي عند الرفع) تُطبع الخلفية الرسمية فقط دون أي إضافات،
    للحفاظ على التوافق مع الاستخدام السابق للدالة.

    ملاحظة: يعمل فقط على ملفات PDF. ملفات Word (doc/docx) لا يمكن ختمها
    مباشرة بهذه الطريقة لأنها ليست بصيغة PDF - استخدم stamp_docx_with_qr
    (في app/docx_utils.py) بدلاً من ذلك.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(input_path)
    if getattr(reader, "is_encrypted", False):
        raise ValueError("لا يمكن ختم ملف PDF محمي بكلمة سر")

    # ===== تجهيز رمز QR مسبقًا (يُستخدم فقط في الصفحة الأولى إن طُلب) =====
    qr_img = None
    font_bold = None
    if verify_url:
        qr_img = _make_qr_reader(verify_url)
        _ensure_fonts()
        font_bold = "Arabic-Bold" if os.path.exists(FONT_BOLD) else "Helvetica-Bold"

    writer = PdfWriter()

    for index, page in enumerate(reader.pages):
        page_w = float(page.mediabox.width)
        page_h = float(page.mediabox.height)

        # صفحة خلفية بنفس مقاس الصفحة الأصلية تحتوي على الورق الرسمي
        bg_buffer = io.BytesIO()
        bg_canvas = canvas.Canvas(bg_buffer, pagesize=(page_w, page_h))
        draw_letterhead_background(bg_canvas, page_w, page_h)

        # ===== بطاقة QR + الرقم المرجعي فوق الورق الرسمي (الصفحة الأولى فقط) =====
        if index == 0 and qr_img is not None:
            _draw_qr_reference_card(bg_canvas, page_h, qr_img, document_number, font_bold)

        bg_canvas.showPage()
        bg_canvas.save()
        bg_buffer.seek(0)

        bg_reader = PdfReader(bg_buffer)
        bg_page = bg_reader.pages[0]
        # دمج محتوى الصفحة الأصلية فوق خلفية الورق الرسمي (+ بطاقة QR إن وُجدت)
        bg_page.merge_page(page)
        writer.add_page(bg_page)

    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path
