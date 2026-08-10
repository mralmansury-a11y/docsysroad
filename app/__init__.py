import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "الرجاء تسجيل الدخول للوصول إلى هذه الصفحة"
login_manager.login_message_category = "warning"


def create_app(config_class="config.Config"):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["ISSUED_FOLDER"], exist_ok=True)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # تسجيل الـ Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.documents import documents_bp
    from app.routes.admin import admin_bp
    from app.routes.public import public_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(public_bp)

    from app import cli
    cli.register(app)

    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {"current_year": datetime.now().year, "app_name": "منظومة تتبع المستندات"}

    from flask import render_template

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/error.html", code=403, message="لا تملك صلاحية الوصول لهذه الصفحة"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/error.html", code=404, message="الصفحة المطلوبة غير موجودة"), 404

    @app.errorhandler(401)
    def unauthorized(e):
        return render_template("errors/error.html", code=401, message="الرجاء تسجيل الدخول أولًا"), 401

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/error.html", code=500, message="حدث خطأ غير متوقع في الخادم"), 500

    return app
