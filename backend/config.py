# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ===== API KEY =====
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

    # ===== DATABASE =====
    DATABASE_NAME = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'residence_maintenance.db'
)

    # ===== MODEL PATHS =====
    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    MODELS_DIR = os.path.join(BASE_DIR, 'models')

    ISSUE_TYPE_MODEL = os.path.join(
        MODELS_DIR, 'issue_type_model.pkl'
    )
    PRIORITY_MODEL = os.path.join(
        MODELS_DIR, 'priority_model.pkl'
    )
    TFIDF_VECTORIZER = os.path.join(
        MODELS_DIR, 'tfidf_vectorizer.pkl'
    )
    IMAGE_MODEL = os.path.join(
        MODELS_DIR, 'image_model_best.h5'
    )

    # ===== UPLOAD FOLDER =====
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max

    # ===== EMAIL SETTINGS =====
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_SENDER = os.getenv('MAIL_USERNAME', '')
    # Resend email service (for production deployment)
    RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')

    # ===== RESIDENCE BLOCKS =====
    BLOCKS = [
        'Block A', 'Block B', 'Block C',
        'Block D', 'Block E', 'Block F'
    ]

    # ===== ISSUE CATEGORIES =====
    ISSUE_TYPES = [
        'Electrical',
        'Plumbing',
        'Structural',
        'Hygiene & Safety',
        'Administrative'
    ]

    # ===== PRIORITY LEVELS =====
    PRIORITY_LEVELS = ['Critical', 'High', 'Medium', 'Low']

    # ===== USER ROLES =====
    ROLES = ['student', 'matron', 'admin']

    # ===== PRIORITIES THAT TRIGGER EMAIL =====
    EMAIL_ALERT_PRIORITIES = ['Critical', 'High']