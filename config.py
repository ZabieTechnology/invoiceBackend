# config.py
import os
from dotenv import load_dotenv
import secrets

basedir = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(basedir, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    print("Warning: .env file not found. Using environment variables or defaults.")

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        print("Warning: SECRET_KEY not set in .env. Using a temporary default key.")
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
    EXPENSE_INVOICE_UPLOAD_FOLDER = os.path.join(basedir, 'uploads', 'expense_invoices') # For expense invoices
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'pdf'} # Add PDF for invoices

    # --- Azure Document AI Configuration ---
    AZURE_FORM_RECOGNIZER_ENDPOINT = os.environ.get('AZURE_FORM_RECOGNIZER_ENDPOINT')
    AZURE_FORM_RECOGNIZER_KEY = os.environ.get('AZURE_FORM_RECOGNIZER_KEY')
    # --- End Azure Document AI Configuration ---

    if SESSION_TYPE == 'filesystem' and not os.path.exists(SESSION_FILE_DIR):
        try:
            os.makedirs(SESSION_FILE_DIR)
        except OSError as e:
            print(f"Error creating session directory {SESSION_FILE_DIR}: {e}")

    SESSION_MONGODB_DB = os.environ.get('SESSION_MONGODB_DB')
    SESSION_MONGODB_COLLECT = os.environ.get('SESSION_MONGODB_COLLECT', 'sessions')

config = Config()

def ensure_upload_folders_exist():
    """Checks if upload folders exist and creates them if not."""
    folders_to_check = [config.UPLOAD_FOLDER, config.EXPENSE_INVOICE_UPLOAD_FOLDER]
    for folder in folders_to_check:
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
                print(f"Created upload folder: {folder}")
            except OSError as e:
                print(f"Error creating upload folder {folder}: {e}")
