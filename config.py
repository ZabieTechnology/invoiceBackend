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

    SESSION_TYPE = os.environ.get('SESSION_TYPE', 'filesystem')
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_FILE_DIR = os.path.join(basedir, '.flask_session')
    
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads', 'logos') # For company logos
    EXPENSE_INVOICE_UPLOAD_FOLDER = os.path.join(basedir, 'uploads', 'expense_invoices')
    
    # --- Invoice Settings Upload Configuration ---
    SIGNATURE_UPLOAD_FOLDER = os.path.join(basedir, 'uploads', 'signatures')
    ALLOWED_SIGNATURE_EXTENSIONS = {'png', 'jpg', 'jpeg'} # More restrictive for signatures
    # --- End Invoice Settings Upload Configuration ---

    AZURE_FORM_RECOGNIZER_ENDPOINT = os.environ.get('AZURE_FORM_RECOGNIZER_ENDPOINT')
    AZURE_FORM_RECOGNIZER_KEY = os.environ.get('AZURE_FORM_RECOGNIZER_KEY')

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

def ensure_upload_folders_exist():
    """Checks if all configured upload folders exist and creates them if not."""
    folders_to_check = [
        config.UPLOAD_FOLDER, 
        config.EXPENSE_INVOICE_UPLOAD_FOLDER,
        config.SIGNATURE_UPLOAD_FOLDER # Add new folder here
    ]
    for folder in folders_to_check:
        if folder and not os.path.exists(folder): # Check if folder path is defined
            try:
                os.makedirs(folder)
                print(f"Created upload folder: {folder}")
            except OSError as e:
                print(f"Error creating upload folder {folder}: {e}")
