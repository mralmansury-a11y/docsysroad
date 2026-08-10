import click
from app import db
from app.models import User, Department


def register(app):
    @app.cli.command("init-db")
    def init_db():
        """إنشاء جداول قاعدة البيانات"""
        db.create_all()
        click.echo("تم إنشاء قاعدة البيانات بنجاح.")

    @app.cli.command("seed")
    def seed():
        """إضافة بيانات تجريبية: أقسام ومستخدمين بأدوار مختلفة"""
        db.create_all()

        if Department.query.first():
            click.echo("توجد بيانات مسبقًا - تم تجاوز عملية التهيئة.")
            return

        dept_admin = Department(name="الإدارة العامة")
        dept_hr = Department(name="الموارد البشرية")
        dept_it = Department(name="تقنية المعلومات")
        db.session.add_all([dept_admin, dept_hr, dept_it])
        db.session.flush()

        users = [
            User(name="مدير النظام", email="admin@example.com", role="admin", department_id=dept_admin.id),
            User(name="أحمد رئيس قسم الموارد البشرية", email="head.hr@example.com", role="department_head", department_id=dept_hr.id),
            User(name="سارة موظفة", email="employee@example.com", role="employee", department_id=dept_hr.id),
            User(name="خالد موظف الأرشيف", email="archivist@example.com", role="archivist", department_id=dept_admin.id),
            User(name="منى موظفة تقنية المعلومات", email="it@example.com", role="employee", department_id=dept_it.id),
        ]
        for u in users:
            u.set_password("password123")
        db.session.add_all(users)
        db.session.commit()

        dept_hr.head_uid = users[1].id
        db.session.commit()

        click.echo("تمت إضافة البيانات التجريبية بنجاح.")
        click.echo("-" * 50)
        click.echo("حسابات الدخول (كلمة السر لجميع الحسابات: password123):")
        for u in users:
            click.echo(f"  {u.email:<25} -> {u.role_label()}")
        click.echo("-" * 50)
