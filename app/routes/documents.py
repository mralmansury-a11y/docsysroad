import os
import uuid
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, send_from_directory, send_file, after_this_request, abort
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.models import Document, Department, User, AuditLog, DOC_TYPES, RECIPIENT_TYPES
from app.utils import allowed_file, generate_document_number, human_size
from app.pdf_utils import generate_issued_pdf, stamp_pdf_with_qr
from app.docx_utils import stamp_docx_with_qr

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")


# ============ قائمة المستندات مع الفلاتر (FR-5) ============
@documents_bp.route("/")
@login_required
def list_documents():
    query = Document.query

    if not current_user.can_view_all_departments():
        query = query.filter(Document.department_id == current_user.department_id)

    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Document.title.ilike(like), Document.number.ilike(like)))

    doc_type = request.args.get("type", "")
    if doc_type:
        query = query.filter(Document.type == doc_type)

    department_id = request.args.get("department_id", "")
    if department_id:
        query = query.filter(Document.department_id == int(department_id))

    date_from = request.args.get("date_from", "")
    if date_from:
        query = query.filter(Document.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))

    date_to = request.args.get("date_to", "")
    if date_to:
        end = datetime.strptime(date_to, "%Y-%m-%d")
        end = end.replace(hour=23, minute=59, second=59)
        query = query.filter(Document.created_at <= end)

    sort = request.args.get("sort", "date_desc")
    if sort == "date_asc":
        query = query.order_by(Document.created_at.asc())
    elif sort == "number":
        query = query.order_by(Document.number.desc())
    else:
        query = query.order_by(Document.created_at.desc())

    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=20, error_out=False)

    departments = Department.query.order_by(Department.name).all()

    return render_template(
        "documents/list.html",
        documents=pagination.items,
        pagination=pagination,
        departments=departments,
        doc_types=DOC_TYPES,
        filters=request.args,
    )


# ============ الأرشيف (FR-7) ============
@documents_bp.route("/archive")
@login_required
def archive():
    query = Document.query.filter(Document.status == "archived")
    if not current_user.can_view_all_departments():
        query = query.filter(Document.department_id == current_user.department_id)

    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Document.title.ilike(like), Document.number.ilike(like)))

    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Document.created_at.desc()).paginate(page=page, per_page=20, error_out=False)

    return render_template("documents/archive.html", documents=pagination.items, pagination=pagination)


# ============ رفع وإصدار مستند جديد (FR-2) ============
@documents_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_document():
    if not current_user.can_upload_document():
        abort(403)

    if request.method == "POST":
        file = request.files.get("file")
        title = request.form.get("title", "").strip()
        doc_type = request.form.get("type", "")
        category = request.form.get("category", "").strip()
        notes = request.form.get("notes", "").strip()
        recipient_type = request.form.get("recipient_type", "")
        recipient_id = request.form.get("recipient_id", "").strip()
        recipient_name = request.form.get("recipient_name", "").strip()

        errors = []
        if not file or file.filename == "":
            errors.append("الرجاء اختيار ملف (Word أو PDF)")
        elif not allowed_file(file.filename):
            errors.append("صيغة الملف غير مدعومة. الصيغ المسموحة: docx, doc, pdf")

        if not title:
            errors.append("العنوان حقل إجباري")
        if doc_type not in DOC_TYPES:
            errors.append("الرجاء اختيار نوع المستند")
        if recipient_type not in RECIPIENT_TYPES:
            errors.append("الرجاء تحديد المُرسَل إليه")
        elif recipient_type in ("department", "user") and not recipient_id:
            errors.append("الرجاء اختيار الجهة/الشخص المُرسَل إليه من القائمة")
        elif recipient_type == "external" and not recipient_name:
            errors.append("الرجاء إدخال اسم الجهة الخارجية")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "documents/new.html",
                departments=Department.query.order_by(Department.name).all(),
                users=User.query.filter_by(active=True).order_by(User.name).all(),
                doc_types=DOC_TYPES,
                recipient_types=RECIPIENT_TYPES,
                form=request.form,
            )

        # ---- تحديد اسم جهة الاستقبال المعروضة ----
        if recipient_type == "department":
            dept = Department.query.get(int(recipient_id))
            recipient_name = dept.name if dept else recipient_name
        elif recipient_type == "user":
            usr = User.query.get(int(recipient_id))
            recipient_name = usr.name if usr else recipient_name

        # ---- حفظ الملف الأصلي (FR-3) ----
        original_filename = secure_filename(file.filename)
        file_ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
        unique_name = f"{uuid.uuid4().hex}_{original_filename}"
        dept_folder = os.path.join(current_app.config["UPLOAD_FOLDER"], str(current_user.department_id or "no-dept"))
        os.makedirs(dept_folder, exist_ok=True)
        saved_path = os.path.join(dept_folder, unique_name)
        file.save(saved_path)

        # ملاحظة: لا يُطبَّق أي ختم على الملف هنا. رقم المستند ورابط التحقق (QR)
        # غير معروفين بعد في هذه المرحلة - يتم ختم الملف الأصلي (لملفات PDF)
        # بعد إنشائهما داخل معاملة الإصدار أدناه (انظر stamp_pdf_with_qr).

        rel_file_path = os.path.relpath(saved_path, current_app.config["UPLOAD_FOLDER"]).replace("\\", "/")

        # ==== عملية الإصدار الواحدة (Transaction) - FR-2.4 ====
        try:
            number = generate_document_number(doc_type)

            document = Document(
                number=number,
                title=title,
                type=doc_type,
                category=category or None,
                department_id=current_user.department_id,
                status="archived",  # يُؤرشف تلقائيًا فور الإصدار
                notes=notes or None,
                file_path=rel_file_path,
                sender_uid=current_user.id,
                sender_name=current_user.name,
                recipient_type=recipient_type,
                recipient_id=recipient_id or None,
                recipient_name=recipient_name,
                created_by=current_user.id,
            )
            db.session.add(document)
            db.session.flush()  # للحصول على document.id قبل commit

            verify_url = f"{current_app.config['APP_DOMAIN']}/verify/{document.id}"
            document.qr_data = verify_url

            # ---- إضافة رمز QR والرقم المرجعي أعلى الصفحة الأولى من الملف الأصلي (PDF فقط) ----
            # لا يُطبَع أي ورق رسمي (letterhead) هنا - يبقى محتوى الملف الأصلي كما هو
            # تمامًا باستثناء بطاقة QR الصغيرة أعلى الصفحة الأولى، بنفس فكرة ختم
            # ملفات .docx (ترويسة الصفحة الأولى فقط دون المساس ببقية الملف).
            if file_ext == "pdf":
                try:
                    stamped_tmp_path = saved_path + ".stamped.pdf"
                    stamp_pdf_with_qr(saved_path, stamped_tmp_path, verify_url, number)
                    os.replace(stamped_tmp_path, saved_path)
                except Exception:
                    current_app.logger.exception(
                        "فشل إضافة رمز QR والرقم المرجعي إلى الملف الأصلي - سيتم أرشفة الملف بدون ختم"
                    )

            # ---- توليد PDF الإصدار مع QR فوق الورق الرسمي (FR-2.4 / FR-6.3) ----
            issued_filename = f"{number.replace('/', '-')}_{uuid.uuid4().hex[:8]}.pdf"
            issued_dept_folder = os.path.join(current_app.config["ISSUED_FOLDER"], str(current_user.department_id or "no-dept"))
            os.makedirs(issued_dept_folder, exist_ok=True)
            issued_full_path = os.path.join(issued_dept_folder, issued_filename)
            generate_issued_pdf(document, issued_full_path, verify_url)

            document.issued_pdf_path = os.path.relpath(
                issued_full_path, current_app.config["ISSUED_FOLDER"]
            ).replace("\\", "/")

            # ---- سجل التدقيق (FR-4.1) ----
            log = AuditLog(
                document_id=document.id,
                action="created",
                from_status=None,
                to_status="archived",
                by_uid=current_user.id,
                by_name=current_user.name,
                note="تم رفع المستند وإصداره وأرشفته تلقائيًا",
            )
            db.session.add(log)

            db.session.commit()
            flash(f"تم إصدار المستند بنجاح برقم {number} وأرشفته تلقائيًا", "success")
            return redirect(url_for("documents.detail", doc_id=document.id))

        except Exception as exc:
            db.session.rollback()
            if os.path.exists(saved_path):
                os.remove(saved_path)
            current_app.logger.exception("فشل إصدار المستند")
            flash(f"حدث خطأ أثناء إصدار المستند: {exc}", "danger")

    return render_template(
        "documents/new.html",
        departments=Department.query.order_by(Department.name).all(),
        users=User.query.filter_by(active=True).order_by(User.name).all(),
        doc_types=DOC_TYPES,
        recipient_types=RECIPIENT_TYPES,
        form={},
    )


# ============ تفاصيل مستند ============
@documents_bp.route("/<int:doc_id>")
@login_required
def detail(doc_id):
    document = Document.query.get_or_404(doc_id)

    if not current_user.can_view_all_departments() and document.department_id != current_user.department_id:
        abort(403)

    # تسجيل عملية العرض من موظف الأرشيف في سجل التدقيق (FR-4.1)
    if current_user.role == "archivist":
        log = AuditLog(
            document_id=document.id, action="viewed", by_uid=current_user.id,
            by_name=current_user.name, note="عرض من موظف الأرشيف",
        )
        db.session.add(log)
        db.session.commit()

    verify_url = f"{current_app.config['APP_DOMAIN']}/verify/{document.id}"
    return render_template("documents/detail.html", document=document, verify_url=verify_url,
                            human_size=human_size)


@documents_bp.route("/<int:doc_id>/download/original")
@login_required
def download_original(doc_id):
    document = Document.query.get_or_404(doc_id)
    if not current_user.can_view_all_departments() and document.department_id != current_user.department_id:
        abort(403)
    directory = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(directory, document.file_path, as_attachment=True)


@documents_bp.route("/<int:doc_id>/download/issued")
@login_required
def download_issued(doc_id):
    document = Document.query.get_or_404(doc_id)
    if not current_user.can_view_all_departments() and document.department_id != current_user.department_id:
        abort(403)
    directory = current_app.config["ISSUED_FOLDER"]
    return send_from_directory(directory, document.issued_pdf_path, as_attachment=True)


@documents_bp.route("/<int:doc_id>/download/original-marked")
@login_required
def download_original_marked(doc_id):
    """
    تحميل نسخة من الملف الأصلي بالباركود والرقم المرجعي، بدون أي طباعة
    للورق الرسمي (letterhead) في هذا الزر تحديدًا.

    - ملفات PDF: الملفات المرفوعة بعد هذا التحديث تحمل بالفعل رمز QR
      والرقم المرجعي في أصلها المؤرشف (يُضافان تلقائيًا عند الرفع - انظر
      new_document)، لذا يكتفي هذا المسار بتنزيل الملف الأصلي كما هو
      دون أي معالجة إضافية - لا طباعة للورق الرسمي ولا إعادة إضافة رمز QR
      (تفاديًا لتكراره). ملاحظة: الملفات القديمة المرفوعة قبل هذا
      التحديث لا تحمل QR في أصلها، وستُنزَّل عبر هذا الزر بدون رمز QR.
    - ملفات .docx: يُدرج رمز QR والرقم المرجعي داخل ترويسة الصفحة الأولى
      فقط (بدون ورق رسمي)، مع بقاء الملف .docx قابلاً للتحرير (عبر
      docx_utils) - لا تزال هذه الملفات غير مختومة عند الرفع، لذا يبقى
      هذا المسار هو وسيلة إضافة QR الوحيدة لها.
    - ملفات .doc القديمة: غير مدعومة تقنيًا لهذه الميزة.
    """
    document = Document.query.get_or_404(doc_id)
    if not current_user.can_view_all_departments() and document.department_id != current_user.department_id:
        abort(403)

    original_name = document.original_filename()
    file_ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""

    if file_ext not in ("pdf", "docx"):
        flash("إضافة الباركود والرقم المرجعي متاحة فقط لملفات PDF أو Word (.docx)", "warning")
        return redirect(url_for("documents.detail", doc_id=document.id))

    original_full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], document.file_path)
    if not os.path.exists(original_full_path):
        abort(404)

    download_name = f"{document.number.replace('/', '-')}_{original_name}"

    # ---- PDF: الأصل يحمل QR والرقم المرجعي بالفعل من لحظة الرفع - تنزيل مباشر دون معالجة ----
    if file_ext == "pdf":
        return send_file(
            original_full_path, as_attachment=True, download_name=download_name, mimetype="application/pdf"
        )

    # ---- docx: إضافة QR والرقم المرجعي عند الطلب (لا تُختم عند الرفع) ----
    verify_url = document.qr_data or f"{current_app.config['APP_DOMAIN']}/verify/{document.id}"
    tmp_path = os.path.join(
        current_app.config["UPLOAD_FOLDER"], f".tmp_marked_{uuid.uuid4().hex}.{file_ext}"
    )

    try:
        stamp_docx_with_qr(
            original_full_path, tmp_path, verify_url=verify_url, document_number=document.number
        )
        mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    except Exception:
        current_app.logger.exception("فشل توليد نسخة الملف الأصلي مع الباركود والرقم المرجعي")
        flash("حدث خطأ أثناء توليد نسخة الملف مع الباركود، الرجاء المحاولة لاحقًا", "danger")
        return redirect(url_for("documents.detail", doc_id=document.id))

    @after_this_request
    def _cleanup_tmp(response):
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return response

    return send_file(tmp_path, as_attachment=True, download_name=download_name, mimetype=mimetype)


@documents_bp.route("/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document(doc_id):
    if not current_user.can_delete_document():
        abort(403)
    document = Document.query.get_or_404(doc_id)
    db.session.delete(document)
    db.session.commit()
    flash(f"تم حذف المستند {document.number}", "info")
    return redirect(url_for("documents.list_documents"))


@documents_bp.route("/api/recipients")
@login_required
def api_recipients():
    """يستخدمها الـ JS لتحميل قوائم المستخدمين/الأقسام حسب نوع المُرسَل إليه"""
    from flask import jsonify
    rtype = request.args.get("type")
    if rtype == "department":
        items = [{"id": d.id, "name": d.name} for d in Department.query.order_by(Department.name).all()]
    elif rtype == "user":
        items = [{"id": u.id, "name": f"{u.name} ({u.email})"} for u in User.query.filter_by(active=True).order_by(User.name).all()]
    else:
        items = []
    return jsonify(items)
