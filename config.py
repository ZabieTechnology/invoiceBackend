# config.py
import os
from dotenv import load_dotenv
import secrets
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(basedir, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    print("Warning: .env file not found. Using environment variables or defaults.")

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        print("Warning: SECRET_KEY not set in .env. Using a temporary default key for Flask session.")
        SECRET_KEY = secrets.token_hex(16)

    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    MONGO_URI = os.environ.get('DATABASE_URL')
    if not MONGO_URI:
        print("Warning: DATABASE_URL not set in .env. Defaulting to local MongoDB.")
        MONGO_URI = 'mongodb://localhost:27017/invoice_db_default'

    # SESSION_TYPE = os.environ.get('SESSION_TYPE', 'filesystem')
    SESSION_TYPE = os.environ.get('SESSION_TYPE', 'mongodb')
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_FILE_DIR = os.path.join(basedir, '.flask_session')

    UPLOAD_FOLDER = os.path.join(basedir, 'uploads', 'logos')
    EXPENSE_INVOICE_UPLOAD_FOLDER = os.path.join(basedir, 'uploads', 'expense_invoices')
    SIGNATURE_UPLOAD_FOLDER = os.path.join(basedir, 'uploads', 'signatures')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'pdf'}

    # --- Remove or comment out Azure Document AI Configuration ---
    # AZURE_FORM_RECOGNIZER_ENDPOINT = os.environ.get('AZURE_FORM_RECOGNIZER_ENDPOINT')
    # AZURE_FORM_RECOGNIZER_KEY = os.environ.get('AZURE_FORM_RECOGNIZER_KEY')

    # --- Google Cloud Document AI Configuration ---
    GCP_PROJECT_ID = os.environ.get('GCP_PROJECT_ID')
    GCP_LOCATION = os.environ.get('GCP_LOCATION') # e.g., 'us', 'eu' (the region of your processor)
    GCP_PROCESSOR_ID = os.environ.get('GCP_PROCESSOR_ID') # The ID of your invoice processor
    # GOOGLE_APPLICATION_CREDENTIALS environment variable will be set in your environment
    # to point to your service account key JSON file.
    # --- End Google Cloud Document AI Configuration ---

    EXTRACTION_LOG_FOLDER = os.path.join(basedir, 'uploads', 'debug_extractions')

    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    if not JWT_SECRET_KEY:
        print("Warning: JWT_SECRET_KEY not set in .env. Using a temporary default key. THIS IS INSECURE FOR PRODUCTION.")
        JWT_SECRET_KEY = secrets.token_hex(32)

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    if SESSION_TYPE == 'filesystem' and not os.path.exists(SESSION_FILE_DIR):
        try:
            os.makedirs(SESSION_FILE_DIR)
        except OSError as e:
            print(f"Error creating session directory {SESSION_FILE_DIR}: {e}")

    SESSION_MONGODB_DB = os.environ.get('SESSION_MONGODB_DB')
    SESSION_MONGODB_COLLECT = os.environ.get('SESSION_MONGODB_COLLECT', 'sessions')

config = Config()

def ensure_upload_folders_exist(app_instance): # <--- Accept 'app_instance'
    """Checks if all configured upload folders exist and creates them if not."""
    folders_to_check = [
        app_instance.config.get('UPLOAD_FOLDER'), # <-- Use app_instance.config
        app_instance.config.get('EXPENSE_INVOICE_UPLOAD_FOLDER'),
        app_instance.config.get('SIGNATURE_UPLOAD_FOLDER'),
        app_instance.config.get('EXTRACTION_LOG_FOLDER')
    ]
    for folder in folders_to_check:
        if folder and not os.path.exists(folder):
            try:
                os.makedirs(folder)
                print(f"Created upload folder: {folder}")
            except OSError as e:
                print(f"Error creating upload folder {folder}: {e}")
