import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me-in-production")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'docsys.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # مجلدات التخزين
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")
    ISSUED_FOLDER = os.path.join(BASE_DIR, "app", "static", "issued")
    ALLOWED_EXTENSIONS = {"doc", "docx", "pdf"}
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB حسب FR-3.1

    # عنوان التطبيق (يُستخدم في بناء رابط QR كما في FR-6.1)
    APP_DOMAIN = os.environ.get("APP_DOMAIN", "http://127.0.0.1:5000")

    LANGUAGES = ["ar"]
