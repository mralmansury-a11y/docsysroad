from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

# الأدوار الأربعة حسب FR-1.2
ROLES = ["admin", "department_head", "employee", "archivist"]
ROLE_LABELS = {
    "admin": "مدير النظام",
    "department_head": "رئيس قسم",
    "employee": "موظف",
    "archivist": "موظف أرشيف",
}

DOC_TYPES = {"incoming": "وارد", "outgoing": "صادر", "internal": "داخلي"}
RECIPIENT_TYPES = {"department": "قسم داخلي", "user": "مستخدم", "external": "جهة خارجية"}


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    head_uid = db.Column(db.Integer, db.ForeignKey("users.id", use_alter=True, name="fk_head_uid"), nullable=True)

    users = db.relationship("User", back_populates="department", foreign_keys="User.department_id")

    def __repr__(self):
        return f"<Department {self.name}>"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)  # uid
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="employee")
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)

    department = db.relationship("Department", back_populates="users", foreign_keys=[department_id])

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)

    # صلاحيات حسب قسم 5 من الوثيقة
    def can_upload_document(self):
        return self.role in ("admin", "department_head", "employee")

    def can_view_all_departments(self):
        return self.role in ("admin", "archivist")

    def can_delete_document(self):
        return self.role == "admin"

    def can_manage_users(self):
        return self.role == "admin"

    def is_active_user(self):
        return self.active

    def __repr__(self):
        return f"<User {self.email}>"


class Counter(db.Model):
    """عدادات الترقيم التسلسلي - يمنع التكرار عبر id فريد لكل نوع/سنة"""
    __tablename__ = "counters"

    id = db.Column(db.String(64), primary_key=True)  # مثل documents_incoming_2026
    last_number = db.Column(db.Integer, nullable=False, default=0)


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), unique=True, nullable=False)  # IN-2026-0042
    title = db.Column(db.String(300), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # incoming/outgoing/internal
    category = db.Column(db.String(100), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="archived")  # مؤرشف تلقائيًا FR-2.4
    notes = db.Column(db.Text, nullable=True)

    file_path = db.Column(db.String(500), nullable=False)       # الملف الأصلي
    issued_pdf_path = db.Column(db.String(500), nullable=True)  # PDF الإصدار مع QR

    sender_uid = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    sender_name = db.Column(db.String(150), nullable=False)

    recipient_type = db.Column(db.String(20), nullable=False)  # department/user/external
    recipient_id = db.Column(db.String(50), nullable=True)
    recipient_name = db.Column(db.String(300), nullable=False)

    qr_data = db.Column(db.String(500), nullable=True)  # رابط التحقق

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    department = db.relationship("Department", foreign_keys=[department_id])
    sender = db.relationship("User", foreign_keys=[sender_uid])
    creator = db.relationship("User", foreign_keys=[created_by])
    audit_logs = db.relationship("AuditLog", backref="document", cascade="all, delete-orphan",
                                  order_by="AuditLog.timestamp.desc()")

    def type_label(self):
        return DOC_TYPES.get(self.type, self.type)

    def recipient_type_label(self):
        return RECIPIENT_TYPES.get(self.recipient_type, self.recipient_type)

    def status_label(self):
        return "مؤرشف" if self.status == "archived" else self.status

    def original_filename(self):
        return self.file_path.rsplit("/", 1)[-1] if self.file_path else ""

    def __repr__(self):
        return f"<Document {self.number}>"


class AuditLog(db.Model):
    """سجل التدقيق حسب FR-4 - لا يمكن حذفه (NFR-6)"""
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # created/viewed/edited/status_change
    from_status = db.Column(db.String(20), nullable=True)
    to_status = db.Column(db.String(20), nullable=True)
    by_uid = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    by_name = db.Column(db.String(150), nullable=False)
    note = db.Column(db.String(500), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    by_user = db.relationship("User", foreign_keys=[by_uid])

    ACTION_LABELS = {
        "created": "إصدار وأرشفة",
        "viewed": "عرض",
        "edited": "تعديل بيانات وصفية",
        "verified": "تحقق عبر QR",
    }

    def action_label(self):
        return self.ACTION_LABELS.get(self.action, self.action)
