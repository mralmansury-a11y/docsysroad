import os
from functools import wraps
from datetime import datetime

from flask import current_app, abort
from flask_login import current_user

from app import db
from app.models import Counter

TYPE_PREFIX = {"incoming": "IN", "outgoing": "OUT", "internal": "INT"}


def allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def generate_document_number(doc_type):
    """
    توليد رقم تسلسلي فريد مثل IN-2026-0042 (FR-2.4)
    يستخدم صف Counter مع قفل على مستوى الصف لتفادي التكرار عند التزامن (المخاطر - بند 7)
    """
    year = datetime.utcnow().year
    prefix = TYPE_PREFIX.get(doc_type, "DOC")
    counter_id = f"documents_{doc_type}_{year}"

    # SELECT ... FOR UPDATE (يدعمه Postgres/MySQL؛ في SQLite يُعامل ضمن Transaction واحدة)
    counter = db.session.query(Counter).filter_by(id=counter_id).with_for_update(read=False).first() \
        if db.engine.name != "sqlite" else db.session.get(Counter, counter_id)

    if counter is None:
        counter = Counter(id=counter_id, last_number=0)
        db.session.add(counter)
        db.session.flush()

    counter.last_number += 1
    number = f"{prefix}-{year}-{counter.last_number:04d}"
    return number


def role_required(*roles):
    """مُزخرِف يقيّد الوصول لأدوار معيّنة فقط"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def human_size(num_bytes):
    for unit in ["B", "KB", "MB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"
