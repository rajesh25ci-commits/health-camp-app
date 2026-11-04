import os

class Config:
    SECRET_KEY = 'smart-health-camp-secret-key'
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    QRCODE_FOLDER = os.path.join(BASE_DIR, 'static', 'qrcodes')
    QR_CODE_FOLDER = os.path.join(BASE_DIR, 'static', 'qrcodes')
    PDF_FOLDER = os.path.join(BASE_DIR, 'static', 'pdf')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
