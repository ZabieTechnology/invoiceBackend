# api/invoice_settings.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
import os
from werkzeug.utils import secure_filename # For signature image upload
from datetime import datetime

from db.invoice_settings_dal import get_invoice_settings, save_invoice_settings

invoice_settings_bp = Blueprint(
    'invoice_settings_bp',
    __name__,
    url_prefix='/api/invoice-settings'
)

logging.basicConfig(level=logging.INFO)

# --- Configuration for Signature Uploads ---
# Ensure this folder exists or is created by your app setup
# It's good to have a separate folder for invoice-related uploads
SIGNATURE_UPLOAD_FOLDER_CONFIG_KEY = 'SIGNATURE_UPLOAD_FOLDER' # Key to get path from app.config
ALLOWED_SIGNATURE_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    allowed_extensions = current_app.config.get('ALLOWED_SIGNATURE_EXTENSIONS', ALLOWED_SIGNATURE_EXTENSIONS)
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_current_user_id(): # Or username, depending on your auth
    # Placeholder: Integrate with your actual authentication system
    # For JWT, you might use get_jwt_identity()
    return session.get('user_id', 'anonymous_user') 

def get_current_tenant_id():
    # Placeholder: If multi-tenant, get tenant ID from session or user object
    return "default_tenant" # Replace with actual tenant logic


@invoice_settings_bp.route('', methods=['GET'])
def handle_get_invoice_settings():
    """Handles GET requests to fetch invoice settings."""
    try:
        tenant_id = get_current_tenant_id() # Implement this based on your app
        settings = get_invoice_settings(tenant_id=tenant_id)
        if settings and '_id' in settings: # Ensure _id is stringified
            settings['_id'] = str(settings['_id'])
        return jsonify(settings), 200
    except Exception as e:
        logging.error(f"Error in handle_get_invoice_settings: {e}")
        return jsonify({"message": "Failed to fetch invoice settings"}), 500

@invoice_settings_bp.route('', methods=['POST', 'PUT']) # Using POST for create/update via upsert
def handle_save_invoice_settings():
    """
    Handles POST/PUT requests to save invoice settings.
    Accepts multipart/form-data if a signature image is included.
    Otherwise, accepts application/json.
    """
    try:
        user = get_current_user_id()
        tenant_id = get_current_tenant_id()
        signature_filename_to_save = None
        
        # Check content type for handling file upload vs JSON
        if 'multipart/form-data' in request.content_type:
            data = request.form.to_dict(flat=True) # Get non-file form fields
            # Convert string booleans from form data
            boolean_fields = ['enableReceiverSignature'] # Add more if needed
            for field in boolean_fields:
                if field in data:
                    data[field] = data[field].lower() == 'true'
            
            # Handle itemTableColumns (assuming sent as JSON string in form data)
            if 'itemTableColumns' in data and isinstance(data['itemTableColumns'], str):
                import json
                try:
                    data['itemTableColumns'] = json.loads(data['itemTableColumns'])
                except json.JSONDecodeError:
                    return jsonify({"message": "Invalid JSON format for itemTableColumns"}), 400
            
            if 'customItemColumns' in data and isinstance(data['customItemColumns'], str):
                import json
                try:
                    data['customItemColumns'] = json.loads(data['customItemColumns'])
                except json.JSONDecodeError:
                    return jsonify({"message": "Invalid JSON format for customItemColumns"}), 400


            if 'signatureImage' in request.files:
                file = request.files['signatureImage']
                if file and file.filename and allowed_file(file.filename):
                    upload_folder = current_app.config.get(SIGNATURE_UPLOAD_FOLDER_CONFIG_KEY)
                    if not upload_folder:
                        logging.error("Signature upload folder is not configured.")
                        return jsonify({"message": "File upload path not configured."}), 500
                    
                    # Create a unique filename
                    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
                    secure_base_filename = secure_filename(file.filename)
                    filename = f"signature_{tenant_id}_{timestamp}_{secure_base_filename}"
                    
                    if not os.path.exists(upload_folder):
                        os.makedirs(upload_folder)
                        logging.info(f"Created signature upload folder: {upload_folder}")
                    
                    file_path = os.path.join(upload_folder, filename)
                    file.save(file_path)
                    signature_filename_to_save = filename # Store relative path or just filename
                    logging.info(f"Signature '{filename}' uploaded successfully for tenant {tenant_id}.")
                elif file and file.filename: # File selected but not allowed type
                    allowed_types_str = ', '.join(current_app.config.get('ALLOWED_SIGNATURE_EXTENSIONS', ALLOWED_SIGNATURE_EXTENSIONS))
                    return jsonify({"message": f"File type not allowed for signature. Allowed: {allowed_types_str}"}), 400
        else: # Assuming application/json
            data = request.get_json()
            if not data:
                return jsonify({"message": "No data provided"}), 400

        # If a new signature was uploaded, add/update its path in the data to be saved
        if signature_filename_to_save:
            data['signatureImageUrl'] = signature_filename_to_save 
        elif 'signatureImageUrl' not in data and request.method in ['POST', 'PUT']:
            # If signatureImageUrl is not in the payload for an update,
            # it implies the client wants to keep the existing one or clear it.
            # If you want to clear it if not sent, add: data['signatureImageUrl'] = None
            pass


        result_id_or_objid = save_invoice_settings(data, user=user, tenant_id=tenant_id)

        if result_id_or_objid:
            # Fetch the latest settings to return
            saved_settings = get_invoice_settings(tenant_id=tenant_id)
            if saved_settings and '_id' in saved_settings:
                saved_settings['_id'] = str(saved_settings['_id'])
            return jsonify({"message": "Invoice settings saved successfully", "data": saved_settings}), 200
        else:
            return jsonify({"message": "Failed to save invoice settings"}), 500

    except Exception as e:
        logging.exception(f"Error in handle_save_invoice_settings: {e}")
        return jsonify({"message": "An internal error occurred"}), 500

