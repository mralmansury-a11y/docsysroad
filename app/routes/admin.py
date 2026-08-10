from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app import db
from app.models import User, Department, ROLES, ROLE_LABELS
from app.utils import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users")
@login_required
@role_required("admin")
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    departments = Department.query.order_by(Department.name).all()
    return render_template("admin/users.html", users=all_users, departments=departments,
                            roles=ROLES, role_labels=ROLE_LABELS)


@admin_bp.route("/users/new", methods=["POST"])
@login_required
@role_required("admin")
def new_user():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "employee")
    department_id = request.form.get("department_id") or None

    if not name or not email or not password:
        flash("الاسم والبريد الإلكتروني وكلمة السر حقول إجبارية", "danger")
        return redirect(url_for("admin.users"))

    if User.query.filter_by(email=email).first():
        flash("هذا البريد الإلكتروني مستخدم بالفعل", "danger")
        return redirect(url_for("admin.users"))

    if role not in ROLES:
        role = "employee"

    user = User(name=name, email=email, role=role, department_id=department_id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f"تم إنشاء حساب {name} بنجاح", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/update", methods=["POST"])
@login_required
@role_required("admin")
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    user.role = request.form.get("role", user.role)
    dept_id = request.form.get("department_id") or None
    user.department_id = int(dept_id) if dept_id else None
    user.active = request.form.get("active") == "on"
    db.session.commit()
    flash(f"تم تحديث بيانات {user.name}", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/departments", methods=["GET", "POST"])
@login_required
@role_required("admin")
def departments():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        head_uid = request.form.get("head_uid") or None
        if name:
            dept = Department(name=name, head_uid=head_uid)
            db.session.add(dept)
            db.session.commit()
            flash(f"تم إنشاء قسم {name}", "success")
        return redirect(url_for("admin.departments"))

    all_departments = Department.query.order_by(Department.name).all()
    all_users = User.query.order_by(User.name).all()
    return render_template("admin/departments.html", departments=all_departments, users=all_users)
