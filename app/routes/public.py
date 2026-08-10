from flask import Blueprint, render_template, abort, current_app, send_from_directory

from app import db
from app.models import Document, AuditLog

public_bp = Blueprint("public", __name__)


@public_bp.route("/verify/<int:doc_id>")
def verify(doc_id):
    """
    صفحة التحقق العامة (FR-6.2) - بدون تسجيل دخول
    تعرض: الرقم التسلسلي، العنوان، التاريخ، جهة الإرسال/الاستقبال، الحالة،
    بالإضافة إلى معاينة/رابط تحميل الملف المؤرشف نفسه
    """
    document = Document.query.get_or_404(doc_id)

    log = AuditLog(
        document_id=document.id, action="verified", by_uid=document.created_by,
        by_name="زائر (تحقق عام)", note="تم مسح رمز QR والتحقق من المستند",
    )
    db.session.add(log)
    db.session.commit()

    return render_template("public/verify.html", document=document)


@public_bp.route("/verify/<int:doc_id>/file")
def verify_download(doc_id):
    """تحميل/معاينة الملف المؤرشف نفسه من صفحة التحقق العامة (FR-6.2)"""
    document = Document.query.get_or_404(doc_id)
    directory = current_app.config["ISSUED_FOLDER"]
    if not document.issued_pdf_path:
        abort(404)
    return send_from_directory(directory, document.issued_pdf_path)
