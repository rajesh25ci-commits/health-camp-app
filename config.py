import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smart-health-camp-secret-key')
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(BASE_DIR, 'database.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    QRCODE_FOLDER = os.path.join(BASE_DIR, 'static', 'qrcodes')
    QR_CODE_FOLDER = os.path.join(BASE_DIR, 'static', 'qrcodes')
    PDF_FOLDER = os.path.join(BASE_DIR, 'static', 'pdf')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # SMTP Email Configuration for OTP Verification
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't', 'yes')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_USERNAME', 'noreply@smarthealthcamp.org'))
    BASE_APP_URL = os.environ.get('BASE_APP_URL', 'http://127.0.0.1:5000')
