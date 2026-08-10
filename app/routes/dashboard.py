from datetime import datetime, timedelta

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.models import Document, Department, DOC_TYPES

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    query = Document.query
    if not current_user.can_view_all_departments():
        query = query.filter(Document.department_id == current_user.department_id)

    total_docs = query.count()

    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_count = query.filter(Document.created_at >= start_of_month).count()

    incoming_count = query.filter(Document.type == "incoming").count()
    outgoing_count = query.filter(Document.type == "outgoing").count()
    internal_count = query.filter(Document.type == "internal").count()

    # رسم بياني: عدد المستندات حسب القسم (FR-8.2)
    by_department = (
        db.session.query(Department.name, func.count(Document.id))
        .join(Document, Document.department_id == Department.id)
        .group_by(Department.name)
        .all()
    )
    if not current_user.can_view_all_departments():
        by_department = [row for row in by_department if row[0] == (current_user.department.name if current_user.department else None)]

    recent_docs = query.order_by(Document.created_at.desc()).limit(8).all()

    my_docs = Document.query.filter(Document.sender_uid == current_user.id) \
        .order_by(Document.created_at.desc()).limit(6).all()

    return render_template(
        "dashboard/index.html",
        total_docs=total_docs,
        this_month_count=this_month_count,
        incoming_count=incoming_count,
        outgoing_count=outgoing_count,
        internal_count=internal_count,
        by_department=by_department,
        recent_docs=recent_docs,
        my_docs=my_docs,
        doc_types=DOC_TYPES,
    )
