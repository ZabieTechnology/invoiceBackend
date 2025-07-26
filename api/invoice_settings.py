# api/invoice_settings.py
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
import json
from db.invoice_settings_dal import get_invoice_settings, save_invoice_settings, get_default_theme
from db.database import get_db

invoice_settings_bp = Blueprint('invoice_settings_bp', __name__, url_prefix='/api/invoice-settings')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Checks if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@invoice_settings_bp.route('', methods=['GET'])
def handle_get_invoice_settings(current_user_id=None): # Replace with actual user handling
    """Handles GET requests to fetch the complete invoice settings."""
    db = get_db()
    # The DAL function now handles all defaulting and data migration logic.
    settings = get_invoice_settings(db, user_id=current_user_id)
    return jsonify(settings), 200

@invoice_settings_bp.route('', methods=['POST'])
def handle_save_invoice_settings(current_user_id=None): # Replace with actual user handling
    """Handles POST requests to save invoice settings, including file uploads."""
    db = get_db()

    try:
        # Extract and parse settings data from the multipart form.
        global_settings_data_str = request.form.get('global')
        saved_themes_list_str = request.form.get('savedThemes')

        if not global_settings_data_str or not saved_themes_list_str:
            current_app.logger.error("Missing 'global' or 'savedThemes' in form data.")
            return jsonify({"message": "Missing required 'global' or 'savedThemes' data."}), 400

        global_settings_data = json.loads(global_settings_data_str)
        saved_themes_list = json.loads(saved_themes_list_str)

        if not isinstance(global_settings_data, dict) or not isinstance(saved_themes_list, list):
            raise ValueError("Parsed 'global' must be a dict and 'savedThemes' must be a list.")

    except (json.JSONDecodeError, ValueError) as e:
        current_app.logger.error(f"Error parsing invoice settings form data: {e}")
        return jsonify({"message": f"Invalid format for settings data: {e}"}), 400

    upload_folder_base = current_app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder_base):
        os.makedirs(upload_folder_base)

    # Process file uploads for each theme profile.
    for theme_profile in saved_themes_list:
        theme_id = theme_profile.get('id')
        if not theme_id:
            current_app.logger.warning(f"Theme profile found without ID during file processing: {theme_profile.get('profileName')}")
            continue

        # Map frontend image fields to backend properties and subfolders.
        image_fields_map = {
            'signatureImage': {'url_field': 'signatureImageUrl', 'subfolder': 'signatures', 'remove_flag_prefix': 'removeSignature'},
            'upiQrCodeImage': {'url_field': 'upiQrCodeImageUrl', 'subfolder': 'upi_qr', 'remove_flag_prefix': 'removeUpiQrCode'},
            'invoiceFooterImage': {'url_field': 'invoiceFooterImageUrl', 'subfolder': 'footers', 'remove_flag_prefix': 'removeFooterImage'}
        }

        for form_field_key_prefix, details in image_fields_map.items():
            form_file_key = f"{form_field_key_prefix}_{theme_id}"
            form_remove_flag_key = f"{details['remove_flag_prefix']}_{theme_id}"

            subfolder_path = os.path.join(upload_folder_base, details['subfolder'])
            if not os.path.exists(subfolder_path):
                os.makedirs(subfolder_path)

            # Handle image removal.
            if request.form.get(form_remove_flag_key) == 'true':
                theme_profile[details['url_field']] = ""
            # Handle new image upload.
            elif form_file_key in request.files:
                file = request.files[form_file_key]
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(f"{theme_id}_{file.filename}")
                    save_path = os.path.join(subfolder_path, filename)
                    try:
                        file.save(save_path)
                        theme_profile[details['url_field']] = f"/uploads/{details['subfolder']}/{filename}"
                    except Exception as e_save:
                        current_app.logger.error(f"Error saving file {filename}: {e_save}")
                        return jsonify({"message": f"Error saving file {filename}"}), 500
                elif file.filename != '':
                    return jsonify({"message": f"File type not allowed for {form_file_key}"}), 400
            # If no new file and no remove flag, the existing URL is kept.

    try:
        # The DAL function now handles all data merging and saving.
        saved_settings_doc = save_invoice_settings(db, global_settings_data, saved_themes_list, user_id=current_user_id)
        if saved_settings_doc:
            return jsonify({"message": "Invoice settings saved successfully!", "data": saved_settings_doc}), 200
        else:
            return jsonify({"message": "Failed to save settings."}), 500
    except Exception as e:
        current_app.logger.error(f"Database error while saving invoice settings: {e}")
        return jsonify({"message": "An error occurred while saving settings to the database.", "error": str(e)}), 500


@invoice_settings_bp.route('/default-theme', methods=['GET'])
def handle_get_default_theme(current_user_id=None): # Replace with actual user handling
    """Handles GET requests to fetch only the default theme profile."""
    db = get_db()
    theme_profile = get_default_theme(db, user_id=current_user_id)
    return jsonify(theme_profile), 200
