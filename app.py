# app.py
import os
from flask import Flask, jsonify, session
from flask_cors import CORS
from flask_session import Session
from flask_jwt_extended import JWTManager

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
from api.document_ai import document_ai_bp
from api.auth import auth_bp
from api.invoice_settings import invoice_settings_bp
from api.gst_rates import gst_rates_bp
from api.inventory import inventory_bp
from api.sales_invoices import sales_invoices_bp
from api.quote_settings import quote_settings_bp
from api.quote import quote_bp
from api.credit_note import credit_note_bp
from api.payment import payment_bp
from api.business_rules import business_rules_bp
from api.tds_rates import tds_rates_bp
from api.tcs_rates import tcs_rates_bp


def create_app():
    """
    Application factory to create and configure the Flask app.
    """
    app = Flask(__name__)
    app.config.from_object(config)
    # This function is called to ensure directories for file uploads exist.
    ensure_upload_folders_exist(app)

    # --- Azure-Ready CORS Configuration ---
    # Read the allowed frontend URLs from an environment variable.
    frontend_urls = os.environ.get('FRONTEND_URLS', 'http://localhost:3000').split(',')

    app.logger.info(f"Allowed CORS origins: {frontend_urls}")

    # Initialize CORS with support for credentials
    CORS(
        app,
        origins=frontend_urls,
        supports_credentials=True # This line is critical for fixing the error
    )
    # --- End CORS Configuration ---

    init_db(app)
    jwt = JWTManager(app)

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
    app.register_blueprint(auth_bp)
    app.register_blueprint(invoice_settings_bp)
    app.register_blueprint(gst_rates_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(sales_invoices_bp)
    app.register_blueprint(quote_settings_bp)
    app.register_blueprint(quote_bp)
    app.register_blueprint(credit_note_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(business_rules_bp)
    app.register_blueprint(tds_rates_bp)
    app.register_blueprint(tcs_rates_bp)

    # --- Error Handlers for JSON API ---
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({"error": "Not Found", "message": "The requested URL was not found on the server."}), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal Server Error: {error}")
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

    @app.route("/")
    def index():
        return jsonify({"status": "ok", "message": "Welcome to the Invoice Backend API!"})

    return app

# The app instance is created by the factory
app = create_app()

if __name__ == "__main__":
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(host=host, port=port, debug=app.config.get('DEBUG', False))
