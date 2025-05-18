# app.py
import os
from flask import Flask, jsonify, session
from flask_cors import CORS
from flask_session import Session
from flask_jwt_extended import JWTManager # <<< Ensure this import is present

# Import config and other initializers
from config import config, ensure_upload_folders_exist # ensure_upload_folders_exist if you split it
from db.database import init_db, mongo

# Import Blueprints
from api.dropdown import dropdown_bp
from api.company_information import company_info_bp
from api.contact_details import contact_details_bp
from api.customers import customers_bp
from api.vendors import vendors_bp
from api.staff import staff_bp
from api.chart_of_accounts import chart_of_accounts_bp
from api.expenses import expenses_bp
from api.document_ai import document_ai_bp
from api.auth import auth_bp # This blueprint contains your /login route

def create_app():
    app = Flask(__name__)
    app.config.from_object(config) # Load configurations (including JWT_SECRET_KEY)
    
    # Call your function to ensure upload folders exist (if you have one)
    ensure_upload_folders_exist() 

    CORS(
        app,
        origins=["http://localhost:3000"], # Or your specific frontend origin
        supports_credentials=True
    )
    init_db(app) # Initialize database connection

    # --- Initialize JWTManager ---
    # This line is crucial. It associates JWTManager with your Flask app instance.
    jwt = JWTManager(app)
    # --- End JWTManager Init ---

    # Initialize Flask-Session if you're using it for other purposes
    if app.config.get('SESSION_TYPE') == 'mongodb':
        app.config['SESSION_MONGODB'] = mongo.cx
        app.config['SESSION_MONGODB_DB'] = config.SESSION_MONGODB_DB or mongo.db.name
        app.config['SESSION_MONGODB_COLLECT'] = config.SESSION_MONGODB_COLLECT
    Session(app)

    # Register Blueprints
    app.register_blueprint(dropdown_bp)
    app.register_blueprint(company_info_bp)
    app.register_blueprint(contact_details_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(vendors_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(chart_of_accounts_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(document_ai_bp)
    app.register_blueprint(auth_bp) # auth_bp uses create_access_token


    # Test routes (can be removed or secured later)
    @app.route('/api/test/set-session/<name>')
    def set_session_route(name):
        session['username'] = name
        return jsonify({"message": f"Flask session username '{name}' set."})

    @app.route('/api/test/get-session')
    def get_session_route():
        username = session.get('username', 'Not set')
        return jsonify({"flask_session_username": username})

    @app.route('/api/test/clear-session')
    def clear_session_route():
        session.clear()
        return jsonify({"message": "Flask session cleared."})

    @app.route("/")
    def index():
        return jsonify({"status": "ok", "message": "Welcome to the Invoice Backend API!"})

    return app

# This creates the app instance when the script is run
app = create_app()

if __name__ == "__main__":
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    # The debug mode is controlled by FLASK_DEBUG in .env via config.py
    app.run(host=host, port=port, debug=app.config['DEBUG'])
