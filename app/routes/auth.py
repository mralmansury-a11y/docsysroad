from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from app import db
from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.active:
            login_user(user)
            flash(f"مرحبًا بعودتك، {user.name}", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.index"))
        elif user and not user.active:
            flash("هذا الحساب معطّل. الرجاء التواصل مع مدير النظام", "danger")
        else:
            flash("البريد الإلكتروني أو كلمة السر غير صحيحة", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    # flash("تم تسجيل الخروج بنجاح", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("كلمة السر الحالية غير صحيحة", "danger")
        elif len(new_password) < 6:
            flash("كلمة السر الجديدة يجب أن تكون 6 أحرف على الأقل", "warning")
        elif new_password != confirm_password:
            flash("كلمة السر الجديدة وتأكيدها غير متطابقين", "warning")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("تم تحديث كلمة السر بنجاح", "success")
            return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html")
