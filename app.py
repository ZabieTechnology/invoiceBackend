# app.py
import os
from flask import Flask, jsonify, session
from flask_cors import CORS
from flask_session import Session

# Updated import from config
from config import config, ensure_upload_folders_exist
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
from api.document_ai import document_ai_bp # <<< Import Document AI Blueprint
# from api.auth import auth_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    
    # Call the updated function to ensure all upload folders exist
    ensure_upload_folders_exist()

    CORS(
        app,
        origins=["http://localhost:3000"],
        supports_credentials=True
    )
    init_db(app)

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
    app.register_blueprint(document_ai_bp) # <<< Register Document AI Blueprint
    # app.register_blueprint(auth_bp)

    # ... (rest of your test routes and index route) ...
    @app.route('/api/test/set-session/<name>')
    def set_session_route(name):
        session['username'] = name
        session['user_id'] = 'temp_id_123'
        return jsonify({"message": f"Username '{name}' set in session."})

    @app.route('/api/test/get-session')
    def get_session_route():
        username = session.get('username', 'Not set')
        user_id = session.get('user_id', 'Not set')
        return jsonify({"username_in_session": username, "user_id_in_session": user_id})

    @app.route('/api/test/clear-session')
    def clear_session_route():
        session.pop('username', None)
        session.pop('user_id', None)
        return jsonify({"message": "Session username cleared."})

    @app.route("/")
    def index():
        return jsonify({"status": "ok", "message": "Welcome to the Invoice Backend API!"})


    return app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(host=host, port=port, debug=app.config['DEBUG'])
